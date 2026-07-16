"""Command-line entry point.

Examples
--------
Forward projection from the default baseline:
    python -m roi_tracker

Ingest a telemetry file and print the executive report:
    python -m roi_tracker --telemetry data/sample_telemetry.json --report

Override any baseline variable on the fly:
    python -m roi_tracker --legacy-cost 5.10 --volume 250000 --complex-share 0.4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import FinancialBaseline, PipelineConfig
from .engine import ROIEngine
from .report import ExecutiveReport


def _build_baseline(args: argparse.Namespace) -> FinancialBaseline:
    b = FinancialBaseline()
    overrides = {
        "legacy_cost_per_txn": args.legacy_cost,
        "monthly_volume": args.volume,
        "complex_task_share": args.complex_share,
        "avg_input_tokens": args.input_tokens,
        "avg_output_tokens": args.output_tokens,
        "capex_total": args.capex,
        "amortization_volume": args.amortize_over,
        "var_per_incident": args.var,
        "incident_rate": args.incident_rate,
        "hitl_cost_per_review": args.hitl_cost,
        "hitl_rate": args.hitl_rate,
        "maintenance_opex_monthly": args.opex,
    }
    for key, val in overrides.items():
        if val is not None:
            setattr(b, key, val)
    return b


def main() -> None:
    p = argparse.ArgumentParser(prog="roi_tracker", description="AI Operational Value Realization Engine")
    p.add_argument("--telemetry", type=Path, help="Path to a telemetry JSON file to ingest.")
    p.add_argument("--report", action="store_true", help="Print the one-page executive report.")
    p.add_argument("--json", action="store_true", help="Print the raw ROI result as JSON.")

    # baseline overrides (all optional)
    p.add_argument("--legacy-cost", type=float)
    p.add_argument("--volume", type=int)
    p.add_argument("--complex-share", type=float)
    p.add_argument("--input-tokens", type=int)
    p.add_argument("--output-tokens", type=int)
    p.add_argument("--capex", type=float)
    p.add_argument("--amortize-over", type=int)
    p.add_argument("--var", type=float)
    p.add_argument("--incident-rate", type=float)
    p.add_argument("--hitl-cost", type=float)
    p.add_argument("--hitl-rate", type=float)
    p.add_argument("--opex", type=float)

    args = p.parse_args()

    config = PipelineConfig(baseline=_build_baseline(args))
    engine = ROIEngine(config)

    if args.telemetry:
        transactions = json.loads(args.telemetry.read_text())
        result = engine.from_telemetry(transactions)
    else:
        result = engine.project()

    if args.json:
        from dataclasses import asdict

        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        print(ExecutiveReport.render(result))
        print()
        print(
            ExecutiveReport.comparison_block(
                engine.compare_approaches(),
                engine.recommend_hybrid(),
                engine.breakeven_month(),
            )
        )


if __name__ == "__main__":
    main()
