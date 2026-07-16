"""The Micro-P&L Ledger.

Computes the Fully Burdened Cost Per Output (CPO): the true, all-in cost of one
AI transaction. CPO sums three things:

    1. API cost         - input tokens x input price + output tokens x output price
    2. Vector DB overhead - retrieval / embedding-store cost per transaction
    3. Amortized infra  - the one-time build (CapEx) plus ongoing OpEx, spread
                          across transactions

This is the denominator of the whole ROI story: legacy human cost minus fully
burdened CPO is the gross saving per transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import FinancialBaseline, ModelSpec
from .cost_fetcher import CostFetcher


@dataclass
class TransactionCost:
    """Fully burdened cost breakdown for one transaction."""

    api_cost: float
    vector_db_cost: float
    amortized_capex: float
    maintenance_opex: float
    model_name: str

    @property
    def infra_cost(self) -> float:
        return self.amortized_capex + self.maintenance_opex

    @property
    def fully_burdened_cpo(self) -> float:
        return self.api_cost + self.vector_db_cost + self.infra_cost


class MicroPnLLedger:
    """Per-transaction cost accounting for the AI pipeline."""

    def __init__(self, baseline: FinancialBaseline, fetcher: CostFetcher | None = None) -> None:
        self.baseline = baseline
        self.fetcher = fetcher or CostFetcher()

    def api_cost(self, model: ModelSpec, input_tokens: int, output_tokens: int) -> float:
        """Raw provider API cost for one call."""
        price = self.fetcher.price_for(model)
        return input_tokens * price.input_cost_per_token + output_tokens * price.output_cost_per_token

    def cost_per_output(
        self,
        model: ModelSpec,
        input_tokens: int,
        output_tokens: int,
    ) -> TransactionCost:
        """Fully Burdened Cost Per Output for a single transaction on ``model``."""
        return TransactionCost(
            api_cost=self.api_cost(model, input_tokens, output_tokens),
            vector_db_cost=self.baseline.vector_db_cost_per_txn,
            amortized_capex=self.baseline.amortized_capex_per_txn,
            maintenance_opex=self.baseline.maintenance_opex_per_txn,
            model_name=model.name,
        )

    def blended_cpo(
        self,
        flagship: ModelSpec,
        fallback: ModelSpec,
        complex_share: float,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Volume-weighted CPO across the complex/simple task mix."""
        complex_cost = self.cost_per_output(flagship, input_tokens, output_tokens).fully_burdened_cpo
        simple_cost = self.cost_per_output(fallback, input_tokens, output_tokens).fully_burdened_cpo
        share = min(max(complex_share, 0.0), 1.0)
        return share * complex_cost + (1 - share) * simple_cost
