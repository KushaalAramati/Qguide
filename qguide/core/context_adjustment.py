"""
Step 5 -- Context-aware scoring.

Re-weights guide scores according to the experimental context (organism, cell type,
Cas enzyme, delivery method, temperature, expression level). All rules live in
`config/context_weights.json` -- editing biology is a config change, not a code change.

The module records *exactly* which multipliers were applied per guide so the
explainability and sensitivity dashboards can show how context reshaped the ranking.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, Optional

from qguide.app.schemas import ContextAdjustment, DesignRequest, Guide
from qguide.core.off_target import scale_report

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "context_weights.json",
)


@lru_cache(maxsize=4)
def load_weights(path: str = _CONFIG_PATH) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _lookup(table: Dict, key: Optional[str]) -> Dict:
    """Case-insensitive lookup. Config keys vary in case -- organism/cell/delivery
    are lowercase ('human', 'stem_cell') while Cas enzymes are CamelCase
    ('SpCas9-HF1') -- so we match both exactly and case-folded."""
    if not key:
        return table.get("default", {})
    if key in table:
        return table[key]
    folded = str(key).lower()
    for k, v in table.items():
        if k.lower() == folded:
            return v
    return table.get("default", {})


def _temperature_multiplier(weights: Dict, temp_c: Optional[float]) -> float:
    if temp_c is None:
        return 1.0
    t = weights["temperature"]
    delta = abs(temp_c - t["optimum_c"])
    mult = 1.0 - delta * t["falloff_per_degree"]
    return max(t["min_multiplier"], min(t["max_multiplier"], mult))


def context_multipliers(request: DesignRequest, weights: Optional[Dict] = None) -> ContextAdjustment:
    """Compute the per-factor multipliers for a given experimental context.

    Returns a `ContextAdjustment` whose `multiplier` is the product of all factors
    (this is identical for every guide in a run -- guides differ in their *base*
    scores, and context scales them uniformly here; per-guide context effects are
    explored in the sensitivity dashboard).
    """
    weights = weights or load_weights()
    applied: Dict[str, float] = {}
    notes = []

    org = _lookup(weights["organism"], request.organism)
    applied["organism"] = float(org.get("on_target", 1.0))

    cell = _lookup(weights["cell_type"], request.cell_type)
    applied["cell_type"] = float(cell.get("on_target", 1.0))
    if "note" in cell:
        notes.append(f"cell_type: {cell['note']}")

    cas = _lookup(weights["cas_enzyme"], request.cas_enzyme)
    applied["cas_enzyme"] = float(cas.get("on_target", 1.0))

    # Off-target risk multiplier: enzyme fidelity (e.g. SpCas9-HF1 -> 0.60) and
    # organism promiscuity. GC tolerance multiplier: organism GC context.
    off_target_multiplier = float(org.get("off_target_risk", 1.0)) * float(cas.get("off_target_risk", 1.0))
    gc_multiplier = float(org.get("gc", 1.0)) * float(cas.get("gc", 1.0))
    applied["off_target_risk"] = round(off_target_multiplier, 4)
    applied["gc"] = round(gc_multiplier, 4)
    if off_target_multiplier < 0.95:
        notes.append(f"enzyme/organism reduce off-target risk (x{off_target_multiplier:.2f})")

    delivery = _lookup(weights["delivery_method"], request.delivery_method)
    applied["delivery_method"] = float(delivery.get("on_target", 1.0))

    applied["temperature"] = _temperature_multiplier(weights, request.temperature)
    if request.temperature is not None:
        notes.append(f"temperature {request.temperature}C -> x{applied['temperature']:.2f}")

    expr_tab = weights["expression_level"]
    applied["expression_level"] = float(
        expr_tab.get(str(request.expression_level).lower(), expr_tab.get("default", 1.0))
        if request.expression_level else expr_tab.get("default", 1.0)
    )

    # Editing-efficiency multiplier is the product of the on-target factors only
    # (off-target and gc are tracked separately, not folded into efficiency).
    efficiency_factors = ["organism", "cell_type", "cas_enzyme", "delivery_method",
                          "temperature", "expression_level"]
    total = 1.0
    for key in efficiency_factors:
        total *= applied.get(key, 1.0)

    return ContextAdjustment(
        multiplier=round(total, 4),
        off_target_multiplier=round(off_target_multiplier, 4),
        gc_multiplier=round(gc_multiplier, 4),
        applied=applied,
        notes=notes,
    )


def apply_context(guide: Guide, adjustment: ContextAdjustment) -> Guide:
    """Attach a context adjustment to a guide and rescale its off-target report.

    Requires the off-target analysis to have run first (it does in the pipeline).
    """
    guide.context = adjustment
    guide.off_target = scale_report(guide.off_target, adjustment.off_target_multiplier)
    return guide


def apply_context_to_guides(guides, request: DesignRequest, weights: Optional[Dict] = None):
    adj = context_multipliers(request, weights)
    for g in guides:
        apply_context(g, adj)
    return guides
