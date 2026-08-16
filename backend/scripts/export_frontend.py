#!/usr/bin/env python
"""Emit the measured numbers in the shape the frontend consumes.

`src/lib/data.ts` currently carries `DECAY_SERIES` with a figcaption that says
"Illustrative. We are running this measurement for real and will publish it either way."
This writes the real thing, so that caption can be replaced with a citation.

    python scripts/export_frontend.py            # print the TypeScript
    python scripts/export_frontend.py --write    # also write artifacts/frontend.json

It prints rather than editing `data.ts` in place: the frontend's copy is a product
decision — how much precision to show, whether to keep the illustrative curve alongside
the measured one — and that belongs to whoever owns the page, not to this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"


def load(name: str) -> dict:
    path = ARTIFACTS / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"{path} missing — run `python scripts/run_all.py` first")
    return json.loads(path.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--every", type=int, default=2,
                    help="sample every Nth week, to match DECAY_WEEKS' spacing")
    args = ap.parse_args()

    st = load("staleness")
    res, summary = st["result"], st["summary"]
    fr = load("frontier")
    ov = load("overview")

    weeks = res["weeks"]
    keep = list(range(0, len(weeks), args.every))

    # data.ts stores regret and the chart plots 1 − regret, so the regret series goes
    # across unchanged and `decay-chart.tsx` needs no edit to its arithmetic. Taken from
    # the recorded regret rather than from 1 − score so nothing is clipped.
    frozen_regret = [round(res["arms"]["frozen (A)"]["regret"][i], 3) for i in keep]
    rolling_regret = [round(res["arms"]["rolling (B)"]["regret"][i], 3) for i in keep]
    decay_weeks = [weeks[i] for i in keep]

    # The chart's y-axis will need lowering: it currently bottoms out at Y_MIN = -0.2,
    # and the measured curve goes further than the illustrative one assumed.
    min_captured = 1.0 - max(frozen_regret)

    sweep = fr["sweep"]
    at40 = min(sweep, key=lambda r: abs(r["savings_vs_frontier"] - 0.40))

    ts = f"""// Measured, not illustrative. Produced by backend/scripts/run_all.py from
// RouterBench ({ov['corpus']['items']:,} real prompts x {ov['corpus']['models']} real models,
// {ov['corpus']['cells']:,} graded cells). Replace the figcaption in decay-chart.tsx.
//
// Frozen router: a router fitted once and never updated, which also cannot select models
// released after its training cut-off. Rolling: the same estimator, absorbing each week's
// graded outcomes and onboarding new models as they ship. Values are normalised regret
// against the per-item oracle, so the chart's `1 - v` conversion still applies.
//
// Headline: the frozen router decays {summary['frozen_decay']:.2f} over {len(weeks)} weeks and
// crosses below "one good model" at week {summary['week_crossed_below_best_single']}. The rolling
// router does not decay. {abs(summary['attribution_new_models']) / (abs(summary['attribution_new_models']) + abs(summary['attribution_fresher_data'])):.0%} of the recoverable gap comes from
// being able to select models that did not exist at training time, not from fresher data.

export const DECAY_WEEKS = {decay_weeks};

export const DECAY_SERIES = {{
  frozen: {frozen_regret},
  rolling: {rolling_regret},
}} as const;

// NOTE for decay-chart.tsx: the measured curve goes lower than the illustrative one did.
// `captured = 1 - regret` reaches {min_captured:.2f}, so Y_MIN needs to be about
// {min(-0.2, round(min_captured - 0.1, 1)):g} rather than -0.2 for the frozen line to stay on the plot.
"""

    savings_note = f"""
// The "{100 * at40['savings_vs_frontier']:.0f}% cut" claim on the home page, measured: at lambda_c =
// {at40['lam_cost']:g} the router costs {100 * at40['savings_vs_frontier']:.1f}% less than sending every
// request to the strongest model, while delivering {100 * at40['quality_vs_frontier']:.1f}% of its measured
// quality on held-out items. The tie rate underpinning it — the share of model pairs that
// score identically on the same item — measures {100 * ov['ties']['pairwise_tie_rate']:.1f}%.
"""

    print(ts)
    print(savings_note)

    payload = {
        "decay_weeks": decay_weeks,
        "decay_series": {"frozen": frozen_regret, "rolling": rolling_regret},
        "staleness_summary": summary,
        "savings": {
            "lam_cost": at40["lam_cost"],
            "savings_pct": at40["savings_vs_frontier"],
            "quality_retained_pct": at40["quality_vs_frontier"],
            "quality": at40["quality"],
            "best_single_model": at40["best_single_model"],
        },
        "tie_rate": ov["ties"]["pairwise_tie_rate"],
        "corpus": ov["corpus"],
        "caveats": [
            "one corpus (RouterBench), 11 models, pool history ending December 2023",
            "items are undated, so the replay holds the item distribution fixed: this "
            "measures decay from the pool moving and from data ageing, not workload "
            "drift or contamination",
            "mostly multiple-choice grading, so per-item outcomes carry substantial luck",
        ],
    }
    if args.write:
        out = ARTIFACTS / "frontend.json"
        out.write_text(json.dumps(payload, indent=2))
        print(f"// wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
