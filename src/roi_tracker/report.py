"""The McKinsey-style Executive Report.

Synthesizes the tracked telemetry into a highly compressed, one-page Markdown
report with the exact five-section structure the CFO asked for.
"""

from __future__ import annotations

from .engine import ROIResult


def _money(x: float) -> str:
    if x == float("inf"):
        return "n/a"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"{sign}${x/1_000:.1f}K"
    return f"{sign}${x:,.2f}"


def _cents(x: float) -> str:
    return f"${x:,.4f}"


class ExecutiveReport:
    """Render a ``ROIResult`` into a one-page Markdown brief."""

    @staticmethod
    def render(r: ROIResult, title: str = "AI Operational Value Realization") -> str:
        d = r.detail
        breakeven = (
            f"{r.breakeven_volume_monthly:,.0f} txns/month"
            if r.breakeven_volume_monthly != float("inf")
            else "not reachable at current unit economics"
        )
        roi = "positive (unbounded)" if r.net_roi_pct == float("inf") else f"{r.net_roi_pct:,.1f}%"

        return f"""# {title}

_One-page executive brief. Pricing source: **{r.price_source}**. Volume basis: {r.monthly_volume:,} txns/month._

## Executive Summary
- **Net ROI:** {roi} per dollar of AI run cost.
- **Break-even:** {breakeven}.
- **Total realized savings:** **{_money(r.total_realized_savings)}/month** ({_money(r.total_realized_savings*12)}/yr) after risk and OpEx.

## Unit Economics (CPO)
- **Legacy human cost:** {_cents(r.legacy_cost_per_txn)}/txn.
- **Fully burdened AI cost (CPO):** {_cents(r.fully_burdened_cpo)}/txn.
- **Gross saving:** {_cents(r.gross_saving_per_txn)}/txn ({_pct(r.gross_saving_per_txn, r.legacy_cost_per_txn)} cheaper).
- Pipeline mix: {d.get('complex_task_share', 0)*100:.0f}% complex -> `{d.get('flagship_model','?')}`, rest -> `{d.get('fallback_model','?')}`.

## Risk-Adjusted Adjustments
- **Hallucination Tax:** -{_cents(r.hallucination_tax_per_txn)}/txn (expected incident VaR + HITL remediation).
- **Maintenance OpEx:** -{_cents(r.maintenance_opex_per_txn)}/txn.
- **Net saving after risk:** **{_cents(r.net_saving_per_txn)}/txn** -> {_money(r.monthly_net_saving)}/month.

## Velocity & Throughput
- **Capital reclaimed from HITL reduction:** {_money(r.hitl_capital_reclaimed_monthly)}/month of human review capacity freed.
- **Monthly AI run cost:** {_money(r.monthly_ai_run_cost)} to process {r.monthly_volume:,} txns.
- Frontier tokens priced at {_cents(r.blended_input_price_per_1m/1e6)}/in, {_cents(r.blended_output_price_per_1m/1e6)}/out per token.

## Strategic Recommendation
{ExecutiveReport._recommend(r)}
"""

    @staticmethod
    def _recommend(r: ROIResult) -> str:
        if r.net_saving_per_txn <= 0:
            return (
                "- **Do not scale yet.** Net saving per transaction is non-positive. "
                "Attack the two biggest cost drivers: raise the fallback-model share of traffic "
                "(route more simple tasks off frontier models) and cut the Hallucination Tax with "
                "tighter guardrails before adding volume."
            )
        lever = (
            "shift more traffic to the fallback tier"
            if r.fully_burdened_cpo > r.hallucination_tax_per_txn
            else "invest in guardrails to shrink the Hallucination Tax"
        )
        return (
            f"- **Scale.** Unit economics are positive at {_cents(r.net_saving_per_txn)}/txn. "
            f"Primary lever: {lever}. "
            "- Grow volume past break-even to amortize CapEx faster. "
            "- Instrument real telemetry (litellm callbacks + guardrail flags) to replace assumed "
            "incident/HITL rates with measured ones and tighten this P&L."
        )


def _pct(part: float, whole: float) -> str:
    if whole == 0:
        return "n/a"
    return f"{part/whole*100:.0f}%"
