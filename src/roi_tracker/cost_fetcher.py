"""Dynamic Cost Fetcher.

Pulls current input/output token pricing from litellm's community-maintained
pricing database. litellm ships an offline ``model_cost`` map that updates with
each release, so this works without network access; when litellm is not
installed, or a model is missing, we fall back to the default prices declared in
``config.ModelSpec``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import ModelSpec


@dataclass
class Price:
    """Resolved per-token pricing for a model."""

    input_cost_per_token: float
    output_cost_per_token: float
    source: str  # "litellm" or "default"

    @property
    def input_per_1m(self) -> float:
        return self.input_cost_per_token * 1_000_000

    @property
    def output_per_1m(self) -> float:
        return self.output_cost_per_token * 1_000_000


class CostFetcher:
    """Resolve live token pricing for pipeline models.

    Usage
    -----
    >>> fetcher = CostFetcher()
    >>> price = fetcher.price_for(model_spec)
    >>> price.input_cost_per_token
    """

    def __init__(self) -> None:
        self._model_cost = self._load_litellm_cost_map()

    @staticmethod
    def _load_litellm_cost_map() -> dict:
        try:
            import litellm  # type: ignore

            # litellm.model_cost is a dict keyed by model id with
            # {"input_cost_per_token": float, "output_cost_per_token": float, ...}
            return dict(getattr(litellm, "model_cost", {}) or {})
        except Exception:
            return {}

    def price_for(self, model: ModelSpec) -> Price:
        """Return live pricing for ``model``, falling back to its declared defaults."""
        entry = self._lookup(model.litellm_id)
        if entry is not None:
            inp = entry.get("input_cost_per_token")
            out = entry.get("output_cost_per_token")
            if inp is not None and out is not None:
                return Price(float(inp), float(out), source="litellm")

        return Price(
            model.input_cost_per_token,
            model.output_cost_per_token,
            source="default",
        )

    def _lookup(self, litellm_id: str) -> dict | None:
        """Best-effort match of a litellm id against the pricing map."""
        if not self._model_cost:
            return None
        if litellm_id in self._model_cost:
            return self._model_cost[litellm_id]

        # Try the bare model name after a provider prefix, e.g. "gemini/gemini-2.5-pro".
        if "/" in litellm_id:
            bare = litellm_id.split("/", 1)[1]
            if bare in self._model_cost:
                return self._model_cost[bare]

        # Loose contains-match as a last resort.
        for key, value in self._model_cost.items():
            if litellm_id in key or key in litellm_id:
                return value
        return None

    def price_table(self, models: list[ModelSpec]) -> dict[str, Price]:
        """Convenience: resolve prices for a whole roster at once."""
        return {m.name: self.price_for(m) for m in models}
