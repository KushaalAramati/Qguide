"""
Stage 3 -- Outcome-mode registry.

Different editing goals value different things, so each goal is a small, pluggable
`OutcomeMode` that computes two things per guide:

  * desired_outcome_score  -- "does this guide achieve the intended edit?"
  * repair_outcome_score   -- "is the predicted DNA-repair outcome the one we want?"

Knockout/screen use the (real, objective-weighted) outcome model. The edit-type modes
(base/prime/CRISPRi-a) are PROVISIONAL heuristics -- clearly flagged -- until dedicated
models (BE-Hive/Lindel for base editing, PRIDICT for prime, CRISPRi/a activity models)
are wired in. A real model is dropped in by replacing one `OutcomeMode` subclass; the
ensemble layer and pipeline don't change.
"""
from __future__ import annotations

from typing import Dict, Optional

from qguide.app.schemas import Guide


class OutcomeMode:
    key: str = "knockout"
    label: str = "Knockout"
    provisional: bool = False

    def desired_outcome_score(self, guide: Guide) -> float:
        raise NotImplementedError

    def repair_outcome_score(self, guide: Guide) -> float:
        raise NotImplementedError

    def badge(self, guide: Guide, final: float) -> Optional[str]:
        return None


class KnockoutMode(OutcomeMode):
    key, label, provisional = "knockout", "Knockout", False

    def desired_outcome_score(self, g):
        return g.outcome.functional_disruption_score

    def repair_outcome_score(self, g):
        return g.outcome.frameshift_prob          # frameshift = good for KO

    def badge(self, g, final):
        if g.outcome.knockout_prob >= 0.6 and final >= 0.6:
            return "Strong knockout candidate"
        return None


class PreciseEditMode(OutcomeMode):
    """HDR / prime-style precise edits: reward efficient, predictable editing."""
    key, label, provisional = "precise_edit", "Precise edit", False

    def desired_outcome_score(self, g):
        return max(0.0, 0.6 * g.scores.on_target + 0.4 * (1.0 - g.outcome.no_edit_prob))

    def repair_outcome_score(self, g):
        return g.outcome.in_frame_indel_prob      # predictable repair preferred

    def badge(self, g, final):
        return "Good HDR/precise candidate" if final >= 0.6 else None


class BaseEditMode(OutcomeMode):
    """PROVISIONAL: reward central edit-window positioning + activity; a real model
    would score the target base in the editor window and bystander C/A risk."""
    key, label, provisional = "base_edit", "Base edit", True

    def desired_outcome_score(self, g):
        # crude edit-window proxy: peak near position ~4-8 of the protospacer
        window = 1.0 - abs(((g.position + g.end) / 2 % 20) - 6) / 14.0
        return max(0.0, min(1.0, 0.5 * g.scores.on_target + 0.5 * window))

    def repair_outcome_score(self, g):
        return g.outcome.in_frame_indel_prob

    def badge(self, g, final):
        return "Base-edit candidate (provisional)"


class PrimeEditMode(BaseEditMode):
    """PROVISIONAL: prime editing (real model would score PBS/RTT + nick position)."""
    key, label, provisional = "prime_edit", "Prime edit", True

    def badge(self, g, final):
        return "Prime-edit candidate (provisional)"


class RegulationMode(OutcomeMode):
    """PROVISIONAL: CRISPRi/a reward TSS proximity (proxy: distance-to-target term)."""
    key, label, provisional = "regulation", "CRISPRi/a", True

    def desired_outcome_score(self, g):
        return max(0.0, 0.5 * g.scores.on_target + 0.5 * g.scores.distance_to_target)

    def repair_outcome_score(self, g):
        return g.outcome.no_edit_prob             # dCas9 -> no DSB is expected/fine

    def badge(self, g, final):
        return "Repression/activation candidate (provisional)"


class ScreenMode(OutcomeMode):
    """Library/screening: consistency + coverage; uses the KO outcome signal."""
    key, label, provisional = "screen", "Screen", False

    def desired_outcome_score(self, g):
        return g.outcome.functional_disruption_score

    def repair_outcome_score(self, g):
        return g.outcome.frameshift_prob

    def badge(self, g, final):
        return "Good screening candidate"


# Goal key -> mode instance. `goal_for()` in ensemble maps DesiredOutcome -> goal key.
MODES: Dict[str, OutcomeMode] = {
    "knockout": KnockoutMode(),
    "precise_edit": PreciseEditMode(),
    "base_edit": BaseEditMode(),
    "prime_edit": PrimeEditMode(),
    "regulation": RegulationMode(),
    "screen": ScreenMode(),
}


def get_mode(goal: str) -> OutcomeMode:
    return MODES.get(goal, MODES["knockout"])
