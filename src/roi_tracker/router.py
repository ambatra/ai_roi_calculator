"""Token Optimizer Agent (The Router).

A lightweight, LLM-agnostic routing agent. It assesses task complexity from
cheap, deterministic signals (length, structural cues, keyword intent) and routes
simple tasks to the cheapest fallback model and complex tasks to a flagship
model, optimizing token spend.

The router does not call any LLM to make its decision, so it adds ~zero cost and
latency to the pipeline it is optimizing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .config import ModelSpec, PipelineConfig
from .cost_fetcher import CostFetcher


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


# Intent keywords that signal genuine reasoning / high-stakes work.
_COMPLEX_MARKERS = re.compile(
    r"\b(analy[sz]e|reason|derive|prove|design|architect|strateg|"
    r"legal|compliance|diagnos|forecast|optimi[sz]e|refactor|"
    r"multi[- ]step|trade[- ]?off|root cause|synthesi[sz]e)\b",
    re.IGNORECASE,
)
_SIMPLE_MARKERS = re.compile(
    r"\b(classif|categori[sz]e|extract|lookup|format|translate|"
    r"yes/no|tag|label|sentiment|spell|rephrase)\b",
    re.IGNORECASE,
)


@dataclass
class RouteDecision:
    complexity: TaskComplexity
    model: ModelSpec
    reason: str


class TokenOptimizerRouter:
    """Route tasks to the cost-optimal model for their complexity.

    Parameters
    ----------
    config:
        Pipeline configuration (model roster).
    fetcher:
        Cost fetcher used to pick the *cheapest* fallback by live blended price.
    complexity_token_threshold:
        Prompts longer than this (input tokens) are treated as complex.
    """

    def __init__(
        self,
        config: PipelineConfig,
        fetcher: CostFetcher | None = None,
        complexity_token_threshold: int = 2_000,
    ) -> None:
        self.config = config
        self.fetcher = fetcher or CostFetcher()
        self.complexity_token_threshold = complexity_token_threshold

        if not config.flagships():
            raise ValueError("Pipeline needs at least one flagship model.")
        if not config.fallbacks():
            raise ValueError("Pipeline needs at least one fallback model.")

    # -- complexity assessment -------------------------------------------------

    def assess(self, prompt: str, input_tokens: int | None = None) -> TaskComplexity:
        """Classify a task as SIMPLE or COMPLEX from cheap signals."""
        tokens = input_tokens if input_tokens is not None else self._estimate_tokens(prompt)

        if tokens >= self.complexity_token_threshold:
            return TaskComplexity.COMPLEX

        complex_hit = bool(_COMPLEX_MARKERS.search(prompt))
        simple_hit = bool(_SIMPLE_MARKERS.search(prompt))

        if complex_hit and not simple_hit:
            return TaskComplexity.COMPLEX
        if simple_hit and not complex_hit:
            return TaskComplexity.SIMPLE

        # Ambiguous: lean on length. Short => simple, long-ish => complex.
        return TaskComplexity.COMPLEX if tokens >= self.complexity_token_threshold // 2 else TaskComplexity.SIMPLE

    # -- model selection -------------------------------------------------------

    def cheapest_fallback(self, output_weight: float = 0.5) -> ModelSpec:
        """Pick the fallback model with the lowest blended live price."""
        return min(self.config.fallbacks(), key=lambda m: self._blended_price(m, output_weight))

    def preferred_flagship(self, output_weight: float = 0.5) -> ModelSpec:
        """Pick the cheapest flagship as the default complex-task handler.

        (Quality tie-breaking is out of scope here; cost is the optimizer's lever.)
        """
        return min(self.config.flagships(), key=lambda m: self._blended_price(m, output_weight))

    def route(self, prompt: str, input_tokens: int | None = None) -> RouteDecision:
        complexity = self.assess(prompt, input_tokens)
        if complexity is TaskComplexity.COMPLEX:
            model = self.preferred_flagship()
            reason = "High-reasoning signal / long prompt -> frontier model."
        else:
            model = self.cheapest_fallback()
            reason = "Low-complexity signal -> cheapest fallback model."
        return RouteDecision(complexity, model, reason)

    # -- helpers ---------------------------------------------------------------

    def _blended_price(self, model: ModelSpec, output_weight: float) -> float:
        price = self.fetcher.price_for(model)
        return (
            (1 - output_weight) * price.input_cost_per_token
            + output_weight * price.output_cost_per_token
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # ~4 characters per token is the standard rough estimate.
        return max(1, len(text) // 4)
