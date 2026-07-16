"""Worked example: customer-support ticket triage.

A fictional fintech, "NorthPay", triages 180,000 support tickets a month. Today
a human reads each ticket, tags it, and drafts a first reply. They are weighing
three options:

    1. Do nothing (keep the human process as-is).
    2. Optimize the humans (macros, better tooling, training).
    3. Bring in AI + a human-in-the-loop for the risky slice.

This script plugs their numbers into the engine and prints the whole answer:
the risk-adjusted P&L, the three-way cost comparison, the break-even projection,
and the recommended human/AI split.

Run it:
    PYTHONPATH=src python3 examples/support_triage.py
"""

from __future__ import annotations

from roi_tracker import FinancialBaseline, PipelineConfig, ROIEngine, ExecutiveReport


def northpay_baseline() -> FinancialBaseline:
    return FinancialBaseline(
        # 1 - current human process
        legacy_cost_per_txn=3.50,     # $42/hr fully burdened x 5 min per ticket
        monthly_volume=180_000,

        # 2 - optimize-the-humans alternative
        human_optimization_reduction=0.25,   # macros + tooling => 25% faster
        human_optimization_capex=50_000,      # cost to redesign + retrain

        # 3-5 - AI path
        complex_task_share=0.25,      # 1 in 4 tickets is genuinely hard
        avg_input_tokens=1_500,       # ticket text + context
        avg_output_tokens=350,        # draft reply + tags
        vector_db_cost_per_txn=0.0005,
        capex_total=160_000,          # build + fine-tune the triage assistant
        amortization_volume=4_000_000,
        maintenance_opex_monthly=10_000,

        # 6 - risk (the Hallucination Tax)
        var_per_incident=20_000,      # a wrong compliance-sensitive reply
        incident_rate=0.00004,        # ~1 per 25,000 outputs
        hitl_cost_per_review=6.0,     # human double-checks a flagged reply
        hitl_rate=0.08,               # 8% of replies get a human check

        # 7 - qualitative
        process_sensitivity=0.30,     # moderately sensitive; keep 30% human
    )


def main() -> None:
    engine = ROIEngine(PipelineConfig(baseline=northpay_baseline()))

    result = engine.project()
    comparison = engine.compare_approaches()
    recommendation = engine.recommend_hybrid()
    breakeven_month = engine.breakeven_month()

    print("=" * 68)
    print("NORTHPAY - SUPPORT TICKET TRIAGE : Human vs AI + HITL")
    print("=" * 68)
    print()
    print(ExecutiveReport.render(result, title="NorthPay Support Triage"))
    print()
    print(ExecutiveReport.comparison_block(comparison, recommendation, breakeven_month))

    print("## Break-even projection (cumulative net cash)")
    print()
    print("| Month | Go AI + HITL | Optimize humans |")
    print("|--:|--:|--:|")
    for pt in engine.breakeven_series(horizon_months=12):
        if pt.month % 2 == 0:  # every other month keeps the table short
            print(f"| {pt.month} | ${pt.ai_cumulative_net:,.0f} | ${pt.optimized_cumulative_net:,.0f} |")


if __name__ == "__main__":
    main()
