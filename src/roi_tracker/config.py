"""Pipeline model definitions and financial-baseline configuration.

Everything here is a *variable*. Nothing is hard-coded into the math. The
dashboard exposes each of these as an editable slider / input, and the Python
engine accepts the same values at run time (see ``engine.ROIEngine``).

Prices are per **1 million tokens** for human readability. They are treated as
defaults only: ``cost_fetcher.CostFetcher`` overrides them with live litellm
pricing whenever the model is found in litellm's community pricing database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Tier = Literal["flagship", "fallback"]


@dataclass
class ModelSpec:
    """A single model in the production pipeline.

    Attributes
    ----------
    name:
        Friendly display name shown in the dashboard.
    litellm_id:
        Identifier litellm understands, used to fetch live pricing.
    tier:
        ``"flagship"`` (complex tasks) or ``"fallback"`` (simple tasks).
    input_price_per_1m:
        Default input-token price per 1M tokens (USD). Overridden by live data.
    output_price_per_1m:
        Default output-token price per 1M tokens (USD). Overridden by live data.
    """

    name: str
    litellm_id: str
    tier: Tier
    input_price_per_1m: float
    output_price_per_1m: float

    @property
    def input_cost_per_token(self) -> float:
        return self.input_price_per_1m / 1_000_000

    @property
    def output_cost_per_token(self) -> float:
        return self.output_price_per_1m / 1_000_000


# Pipeline chosen during the CFO interview.
#   Flagship (complex tasks): claude-opus-4-8, gpt-5 / o-series, gemini-2.5-pro
#   Fallback (simple tasks):  ollama open llm, gpt-5-mini / 4o-mini, gemini-2.5-flash
# Default prices are indicative and get replaced by live litellm data when available.
DEFAULT_MODELS: list[ModelSpec] = [
    ModelSpec("claude-opus-4-8", "claude-opus-4-8", "flagship", 15.0, 75.0),
    ModelSpec("gpt-5", "gpt-5", "flagship", 10.0, 30.0),
    ModelSpec("gemini-2.5-pro", "gemini/gemini-2.5-pro", "flagship", 1.25, 10.0),
    ModelSpec("ollama-open-llm", "ollama/llama3", "fallback", 0.0, 0.0),
    ModelSpec("gpt-5-mini", "gpt-5-mini", "fallback", 0.25, 2.0),
    ModelSpec("gemini-2.5-flash", "gemini/gemini-2.5-flash", "fallback", 0.30, 2.50),
]


@dataclass
class FinancialBaseline:
    """The CFO-interview inputs. Every field is an editable variable.

    Plain-English glossary
    -----------------------
    legacy_cost_per_txn:
        What one transaction costs today with humans only. Fully-burdened
        hourly rate of the operator multiplied by minutes spent per task.
    monthly_volume:
        How many transactions the pipeline handles per month.
    complex_task_share:
        Fraction (0-1) of transactions that are hard enough to need a flagship
        model. The rest go to a cheap fallback model.
    avg_input_tokens / avg_output_tokens:
        Typical prompt size and answer size per transaction, in tokens.
    vector_db_cost_per_txn:
        Retrieval / embedding-store cost charged each time we look something up.
    capex_total:
        One-time money already spent building and fine-tuning the system.
    amortization_volume:
        Over how many transactions we spread that CapEx. CapEx per transaction
        = capex_total / amortization_volume. (Answers "when does the build pay
        for itself.")
    var_per_incident:
        Value at Risk. The financial damage of one catastrophic hallucination
        or compliance failure that reaches production.
    incident_rate:
        Fraction (0-1) of outputs that turn into such an incident.
    hitl_cost_per_review:
        Cost of one human review when a guardrail flags an output.
    hitl_rate:
        Fraction (0-1) of outputs sent to a human-in-the-loop queue.
    maintenance_opex_monthly:
        Ongoing monthly run cost: monitoring, retraining, on-call, licences.
    """

    legacy_cost_per_txn: float = 4.20
    monthly_volume: int = 100_000
    complex_task_share: float = 0.30

    avg_input_tokens: int = 1_200
    avg_output_tokens: int = 400
    vector_db_cost_per_txn: float = 0.0004

    capex_total: float = 180_000.0
    amortization_volume: int = 5_000_000

    var_per_incident: float = 25_000.0
    incident_rate: float = 0.00005  # 1 catastrophic failure per 20,000 outputs

    hitl_cost_per_review: float = 8.0
    hitl_rate: float = 0.05

    maintenance_opex_monthly: float = 12_000.0

    # -- current human process & its optimization alternative -----------------
    # legacy_cost_per_txn above is the AS-IS human cost. These describe the
    # "just make the humans better" alternative to buying AI:
    #   human_optimization_reduction : fraction (0-1) cost cut from lean / tooling.
    #   human_optimization_capex     : one-time spend to redesign the human process.
    human_optimization_reduction: float = 0.20
    human_optimization_capex: float = 40_000.0

    # -- qualitative --------------------------------------------------------
    # process_sensitivity (0-1): how error-costly / judgment-heavy the work is.
    # High sensitivity inflates AI's effective risk and argues for keeping more
    # of the work human. Drives the hybrid recommendation.
    process_sensitivity: float = 0.35

    @property
    def optimized_human_cost_per_txn(self) -> float:
        red = min(max(self.human_optimization_reduction, 0.0), 1.0)
        return self.legacy_cost_per_txn * (1 - red) + self._opt_capex_per_txn

    @property
    def _opt_capex_per_txn(self) -> float:
        if self.amortization_volume <= 0:
            return 0.0
        return self.human_optimization_capex / self.amortization_volume

    @property
    def amortized_capex_per_txn(self) -> float:
        if self.amortization_volume <= 0:
            return 0.0
        return self.capex_total / self.amortization_volume

    @property
    def maintenance_opex_per_txn(self) -> float:
        if self.monthly_volume <= 0:
            return 0.0
        return self.maintenance_opex_monthly / self.monthly_volume


@dataclass
class PipelineConfig:
    """Full engine configuration: the model roster plus the financial baseline."""

    models: list[ModelSpec] = field(default_factory=lambda: list(DEFAULT_MODELS))
    baseline: FinancialBaseline = field(default_factory=FinancialBaseline)

    def flagships(self) -> list[ModelSpec]:
        return [m for m in self.models if m.tier == "flagship"]

    def fallbacks(self) -> list[ModelSpec]:
        return [m for m in self.models if m.tier == "fallback"]
