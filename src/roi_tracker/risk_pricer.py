"""Risk Pricer (The Hallucination Tax).

Not every AI output is free of consequence. Two costs erode gross savings:

    1. Hallucination / compliance risk - the expected loss from outputs that
       reach production and turn out to be catastrophically wrong.
       Expected cost = incident_rate x Value-at-Risk-per-incident.

    2. Human-in-the-loop (HITL) remediation - when a guardrail flags an output,
       a human reviews it. That review has a cost.
       Expected cost = hitl_rate x cost-per-review.

The sum is the per-transaction "Hallucination Tax", deducted from gross ROI.
The pricer also logs individual flagged / HITL events so the tax can be measured
from real telemetry instead of assumed rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import FinancialBaseline


@dataclass
class RiskLedger:
    """Running tallies from observed telemetry."""

    total_outputs: int = 0
    flagged_incidents: int = 0        # catastrophic hallucination / compliance failures
    hitl_reviews: int = 0             # outputs routed to a human queue
    remediation_cost: float = 0.0     # actual human remediation spend logged
    var_realized: float = 0.0         # actual value-at-risk losses logged

    @property
    def observed_incident_rate(self) -> float:
        return self.flagged_incidents / self.total_outputs if self.total_outputs else 0.0

    @property
    def observed_hitl_rate(self) -> float:
        return self.hitl_reviews / self.total_outputs if self.total_outputs else 0.0


class RiskPricer:
    """Prices operational risk per transaction and logs remediation events."""

    def __init__(self, baseline: FinancialBaseline) -> None:
        self.baseline = baseline
        self.ledger = RiskLedger()

    # -- event logging (drives measured rates) --------------------------------

    def log_output(
        self,
        flagged_incident: bool = False,
        sent_to_hitl: bool = False,
        remediation_cost: float | None = None,
        var_loss: float | None = None,
    ) -> None:
        """Record one observed output and any risk events attached to it."""
        self.ledger.total_outputs += 1
        if flagged_incident:
            self.ledger.flagged_incidents += 1
            self.ledger.var_realized += (
                var_loss if var_loss is not None else self.baseline.var_per_incident
            )
        if sent_to_hitl:
            self.ledger.hitl_reviews += 1
            self.ledger.remediation_cost += (
                remediation_cost
                if remediation_cost is not None
                else self.baseline.hitl_cost_per_review
            )

    # -- expected (a-priori) pricing ------------------------------------------

    def expected_incident_tax_per_txn(self) -> float:
        return self.baseline.incident_rate * self.baseline.var_per_incident

    def expected_hitl_cost_per_txn(self) -> float:
        return self.baseline.hitl_rate * self.baseline.hitl_cost_per_review

    def expected_hallucination_tax_per_txn(self) -> float:
        """Total expected risk deduction per transaction."""
        return self.expected_incident_tax_per_txn() + self.expected_hitl_cost_per_txn()

    # -- measured (a-posteriori) pricing --------------------------------------

    def measured_tax_per_txn(self) -> float:
        """Hallucination Tax per transaction from logged telemetry (0 if none)."""
        n = self.ledger.total_outputs
        if not n:
            return 0.0
        return (self.ledger.var_realized + self.ledger.remediation_cost) / n
