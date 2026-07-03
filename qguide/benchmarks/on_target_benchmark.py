#!/usr/bin/env python3
"""
On-target accuracy benchmark (roadmap Task B).

Runs QGuide's REAL on-target scoring logic (qguide.core.scoring.COMPONENTS +
ON_TARGET_WEIGHTS — the exact code path used in production) over a dataset of
spacers with a *measured* activity value, and reports how well the score ranks
real activity: Spearman (rank) and Pearson correlation.

This is the honest "are our guides actually good?" check from the YC review. A
score that does not correlate with measured activity means the recommendations
are not yet trustworthy — fix the scorer before adding features.

USAGE
-----
  # Self-test (no data needed) — proves the harness + correlation math work:
  python -m qguide.benchmarks.on_target_benchmark --selftest

  # Real benchmark against a Doench-style CSV:
  python -m qguide.benchmarks.on_target_benchmark data.csv \
      --seq-col 30mer --activity-col score_drug_gene_rank

WHERE TO GET REAL DATA (download locally; not fetched here)
  - Doench et al. 2016 (Rule Set 2 / Azimuth) training data — the canonical
    on-target activity benchmark. Commonly distributed as a CSV of 30-mers
    (4 nt 5' context + 20 nt protospacer + 3 nt PAM + 3 nt 3' context) with a
    measured/ranked activity column (e.g. via the Broad GPP / Azimuth repo).
  - Any CSV works as long as it has one DNA-sequence column (20-mer spacer OR
    30-mer context) and one numeric activity column.

The harness auto-detects a 30-mer vs 20-mer: a 30-mer is sliced to spacer =
[4:24] and PAM = [24:27]; a 20-mer is used directly with an assumed NGG PAM.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from types import SimpleNamespace
from typing import List, Optional, Tuple

from qguide.core import scoring


# --------------------------------------------------------------------------- #
# Score one spacer with the production on-target logic                          #
# --------------------------------------------------------------------------- #
def on_target_score(spacer: str, pam: str = "AGG") -> float:
    spacer = (spacer or "").upper()
    if not spacer:
        return 0.0
    gc = (spacer.count("G") + spacer.count("C")) / len(spacer)
    # duck-typed guide: the scoring components only read these four attributes.
    g = SimpleNamespace(sequence=spacer, pam=(pam or "AGG").upper(),
                        gc_content=gc, distance_to_target=0.0)
    vals = {name: fn(g) for name, fn in scoring.COMPONENTS.items()}
    raw = sum(scoring.ON_TARGET_WEIGHTS[n] * vals[n] for n in scoring.ON_TARGET_WEIGHTS)
    pos = sum(w for w in scoring.ON_TARGET_WEIGHTS.values() if w > 0)
    return max(0.0, min(1.0, raw / pos))


def spacer_from_context(seq: str) -> Tuple[str, str]:
    """Return (20-mer spacer, 3-mer PAM) from a 20-mer or 30-mer context."""
    seq = (seq or "").upper().strip()
    if len(seq) >= 27:                 # 30-mer: 4 + 20 + 3 + 3
        return seq[4:24], seq[24:27]
    return seq[:20], (seq[20:23] if len(seq) >= 23 else "AGG")


# --------------------------------------------------------------------------- #
# Correlation (no scipy/numpy dependency)                                        #
# --------------------------------------------------------------------------- #
def _pearson(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    return num / (dx * dy) if dx and dy else float("nan")


def _rank(v: List[float]) -> List[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    ranks = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0            # average rank for ties (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: List[float], y: List[float]) -> float:
    return _pearson(_rank(x), _rank(y))


# --------------------------------------------------------------------------- #
# Runner                                                                        #
# --------------------------------------------------------------------------- #
def evaluate(sequences: List[str], activity: List[float]) -> dict:
    preds = [on_target_score(*spacer_from_context(s)) for s in sequences]
    return {"n": len(preds), "spearman": spearman(preds, activity),
            "pearson": _pearson(preds, activity), "preds": preds}


def _print_report(res: dict) -> None:
    print(f"  n sequences : {res['n']}")
    print(f"  Spearman rho: {res['spearman']:+.3f}   (rank correlation — the headline metric)")
    print(f"  Pearson  r  : {res['pearson']:+.3f}")
    rho = res["spearman"]
    verdict = ("STRONG — competitive with published scorers" if rho >= 0.5 else
               "MODERATE — usable but beatable" if rho >= 0.3 else
               "WEAK — scores do not track real activity; fix before shipping" if rho >= 0.1 else
               "NONE — the scorer is not predictive on this data")
    print(f"  Verdict     : {verdict}")
    print("  (Guide: published on-target models land ~0.4-0.6 Spearman on held-out data.)")


def run_csv(path: str, seq_col: Optional[str], act_col: Optional[str]) -> int:
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("No rows in CSV."); return 1
    cols = rows[0].keys()

    def guess_seq():
        for c in cols:
            v = str(rows[0][c]).upper()
            if len(v) >= 20 and all(ch in "ACGT" for ch in v):
                return c
        return None

    def guess_act():
        for c in cols:
            try:
                float(rows[0][c]); 
                if c != seq_col:
                    return c
            except (ValueError, TypeError):
                continue
        return None

    sc = seq_col or guess_seq()
    ac = act_col or guess_act()
    if not sc or not ac:
        print(f"Could not identify columns. Available: {list(cols)}")
        print("Pass --seq-col and --activity-col explicitly."); return 1
    seqs, acts = [], []
    for r in rows:
        try:
            acts.append(float(r[ac])); seqs.append(r[sc])
        except (ValueError, TypeError):
            continue
    print(f"On-target benchmark  (seq='{sc}', activity='{ac}')")
    _print_report(evaluate(seqs, acts))
    return 0


def selftest() -> int:
    # 1) correlation math sanity
    assert abs(spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert abs(_pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    # 2) harness runs end-to-end on a small synthetic set (NOT real activity —
    #    this only proves the pipeline executes and produces a finite number).
    import random
    random.seed(7)
    seqs = ["".join(random.choice("ACGT") for _ in range(20)) for _ in range(40)]
    # synthetic "activity" loosely tied to GC so correlation is finite/non-trivial
    act = [(s.count("G") + s.count("C")) / 20 + random.uniform(-0.1, 0.1) for s in seqs]
    res = evaluate(seqs, act)
    assert res["n"] == 40 and math.isfinite(res["spearman"])
    print("SELF-TEST PASSED — correlation math + scoring pipeline both work.")
    print("Synthetic sanity run (NOT a real accuracy result):")
    _print_report(res)
    print("\nNext: run against the real Doench 2016 CSV to get the true accuracy number.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QGuide on-target accuracy benchmark")
    ap.add_argument("csv", nargs="?", help="CSV with a sequence column + activity column")
    ap.add_argument("--seq-col"); ap.add_argument("--activity-col")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest or not a.csv:
        return selftest()
    return run_csv(a.csv, a.seq_col, a.activity_col)


if __name__ == "__main__":
    sys.exit(main())
