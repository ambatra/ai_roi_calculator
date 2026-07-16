"""AI Operational Value Realization Engine (ROI Tracker).

Ingests LLM telemetry and translates it into a dynamic, risk-adjusted
Profit & Loss statement for AI operations.

Modules
-------
config        : Pipeline model definitions and financial baseline defaults.
cost_fetcher  : Dynamic per-token pricing via litellm (with safe fallbacks).
router        : Token Optimizer Agent that routes tasks by complexity.
ledger        : Micro-P&L ledger; Fully Burdened Cost Per Output (CPO).
risk_pricer   : Hallucination Tax and human-in-the-loop remediation cost.
report        : McKinsey-style one-page executive Markdown report.
engine        : End-to-end orchestration over a telemetry stream.
"""

from .config import FinancialBaseline, ModelSpec, PipelineConfig
from .cost_fetcher import CostFetcher
from .router import TokenOptimizerRouter, TaskComplexity
from .ledger import MicroPnLLedger, TransactionCost
from .risk_pricer import RiskPricer, RiskLedger
from .report import ExecutiveReport
from .engine import (
    ROIEngine,
    ROIResult,
    ApproachComparison,
    HybridRecommendation,
    BreakevenPoint,
)

__all__ = [
    "FinancialBaseline",
    "ModelSpec",
    "PipelineConfig",
    "CostFetcher",
    "TokenOptimizerRouter",
    "TaskComplexity",
    "MicroPnLLedger",
    "TransactionCost",
    "RiskPricer",
    "RiskLedger",
    "ExecutiveReport",
    "ROIEngine",
    "ROIResult",
    "ApproachComparison",
    "HybridRecommendation",
    "BreakevenPoint",
]

__version__ = "0.1.0"
