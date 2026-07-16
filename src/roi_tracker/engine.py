"""ROI Engine.

Ties the modules together into one risk-adjusted P&L. Two entry points:

    ROIEngine.project()         - forward-looking projection from the baseline
                                  assumptions (what the dashboard calculator does).
    ROIEngine.from_telemetry()  - measured result from an ingested telemetry
                                  stream (real transactions, flags, HITL events).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .config import ModelSpec, PipelineConfig
from .cost_fetcher import CostFetcher
from .ledger import MicroPnLLedger
from .risk_pricer import RiskPricer
from .router import TokenOptimizerRouter


@dataclass
class ROIResult:
    """The risk-adjusted P&L, per transaction and at monthly scale."""

    legacy_cost_per_txn: float
    fully_burdened_cpo: float
    hallucination_tax_per_txn: float
    maintenance_opex_per_txn: float

    monthly_volume: int

    # per-transaction economics
    gross_saving_per_txn: float
    net_saving_per_txn: float

    # scaled economics
    monthly_gross_saving: float
    monthly_net_saving: float
    monthly_ai_run_cost: float

    net_roi_pct: float
    breakeven_volume_monthly: float
    total_realized_savings: float

    # supporting detail
    price_source: str
    blended_input_price_per_1m: float = 0.0
    blended_output_price_per_1m: float = 0.0
    hitl_capital_reclaimed_monthly: float = 0.0
    detail: dict = field(default_factory=dict)


class ROIEngine:
    def __init__(self, config: PipelineConfig, fetcher: CostFetcher | None = None) -> None:
        self.config = config
        self.fetcher = fetcher or CostFetcher()
        self.ledger = MicroPnLLedger(config.baseline, self.fetcher)
        self.risk = RiskPricer(config.baseline)
        self.router = TokenOptimizerRouter(config, self.fetcher)

    # -- forward projection (dashboard calculator) ----------------------------

    def project(self) -> ROIResult:
        b = self.config.baseline
        flagship = self.router.preferred_flagship()
        fallback = self.router.cheapest_fallback()

        cpo = self.ledger.blended_cpo(
            flagship, fallback, b.complex_task_share, b.avg_input_tokens, b.avg_output_tokens
        )
        tax = self.risk.expected_hallucination_tax_per_txn()

        return self._assemble(cpo, tax, flagship, fallback, price_source=self.fetcher.price_for(flagship).source)

    # -- measured from telemetry ----------------------------------------------

    def from_telemetry(self, transactions: Iterable[dict]) -> ROIResult:
        """Compute the P&L from real transaction records.

        Each record is a dict with keys:
            model            (str)   friendly model name in the roster
            input_tokens     (int)
            output_tokens    (int)
            flagged_incident (bool, optional)
            sent_to_hitl     (bool, optional)
            remediation_cost (float, optional)
            var_loss         (float, optional)
        """
        by_name = {m.name: m for m in self.config.models}
        total_api = 0.0
        count = 0

        for tx in transactions:
            model = by_name.get(tx["model"])
            if model is None:
                raise KeyError(f"Unknown model in telemetry: {tx['model']!r}")
            total_api += self.ledger.api_cost(model, tx["input_tokens"], tx["output_tokens"])
            self.risk.log_output(
                flagged_incident=bool(tx.get("flagged_incident", False)),
                sent_to_hitl=bool(tx.get("sent_to_hitl", False)),
                remediation_cost=tx.get("remediation_cost"),
                var_loss=tx.get("var_loss"),
            )
            count += 1

        if count == 0:
            raise ValueError("Telemetry stream was empty.")

        b = self.config.baseline
        avg_api = total_api / count
        cpo = avg_api + b.vector_db_cost_per_txn + b.amortized_capex_per_txn + b.maintenance_opex_per_txn
        tax = self.risk.measured_tax_per_txn()

        flagship = self.router.preferred_flagship()
        fallback = self.router.cheapest_fallback()
        result = self._assemble(cpo, tax, flagship, fallback, price_source="telemetry")
        result.detail["observed_incident_rate"] = self.risk.ledger.observed_incident_rate
        result.detail["observed_hitl_rate"] = self.risk.ledger.observed_hitl_rate
        result.detail["transactions_ingested"] = count
        return result

    # -- shared assembly ------------------------------------------------------

    def _assemble(self, cpo: float, tax: float, flagship: ModelSpec, fallback: ModelSpec, price_source: str) -> ROIResult:
        b = self.config.baseline
        gross = b.legacy_cost_per_txn - cpo
        net = gross - tax

        monthly_gross = gross * b.monthly_volume
        monthly_net = net * b.monthly_volume
        monthly_run = cpo * b.monthly_volume

        # ROI = net benefit / cost to produce it.
        net_roi = (net / cpo * 100.0) if cpo > 0 else float("inf")

        # Break-even: monthly volume at which cumulative net saving covers CapEx.
        # (CapEx is already amortized into CPO, so break-even here is the volume
        #  that makes monthly net saving non-negative given fixed monthly OpEx.)
        variable_net = b.legacy_cost_per_txn - (cpo - b.maintenance_opex_per_txn) - tax
        breakeven = (b.maintenance_opex_monthly / variable_net) if variable_net > 0 else float("inf")

        # HITL capital reclaimed: humans no longer reviewing everything. If today
        # every txn was human-touched, reclaimed = (1 - hitl_rate) x legacy cost.
        hitl_reclaimed = (1 - b.hitl_rate) * b.legacy_cost_per_txn * b.monthly_volume

        fp = self.fetcher.price_for(flagship)

        return ROIResult(
            legacy_cost_per_txn=b.legacy_cost_per_txn,
            fully_burdened_cpo=cpo,
            hallucination_tax_per_txn=tax,
            maintenance_opex_per_txn=b.maintenance_opex_per_txn,
            monthly_volume=b.monthly_volume,
            gross_saving_per_txn=gross,
            net_saving_per_txn=net,
            monthly_gross_saving=monthly_gross,
            monthly_net_saving=monthly_net,
            monthly_ai_run_cost=monthly_run,
            net_roi_pct=net_roi,
            breakeven_volume_monthly=breakeven,
            total_realized_savings=monthly_net,
            price_source=price_source,
            blended_input_price_per_1m=fp.input_per_1m,
            blended_output_price_per_1m=fp.output_per_1m,
            hitl_capital_reclaimed_monthly=hitl_reclaimed,
            detail={
                "flagship_model": flagship.name,
                "fallback_model": fallback.name,
                "complex_task_share": b.complex_task_share,
            },
        )
