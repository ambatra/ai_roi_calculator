"""Smoke + math tests for the ROI engine. Run: pytest -q"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roi_tracker import (
    FinancialBaseline,
    PipelineConfig,
    ROIEngine,
    ExecutiveReport,
    TokenOptimizerRouter,
    TaskComplexity,
    CostFetcher,
)


def make_engine(**overrides) -> ROIEngine:
    b = FinancialBaseline(**overrides)
    return ROIEngine(PipelineConfig(baseline=b))


def test_projection_positive_when_ai_cheaper():
    engine = make_engine(legacy_cost_per_txn=4.20, incident_rate=0.0, hitl_rate=0.0)
    r = engine.project()
    assert r.fully_burdened_cpo < r.legacy_cost_per_txn
    assert r.gross_saving_per_txn > 0
    assert r.net_saving_per_txn == pytest.approx(r.gross_saving_per_txn, rel=1e-9)


def test_hallucination_tax_reduces_net():
    no_risk = make_engine(incident_rate=0.0, hitl_rate=0.0).project()
    with_risk = make_engine(incident_rate=0.01, hitl_rate=0.10).project()
    assert with_risk.hallucination_tax_per_txn > 0
    assert with_risk.net_saving_per_txn < no_risk.net_saving_per_txn


def test_cpo_components_sum():
    engine = make_engine()
    b = engine.config.baseline
    flagship = engine.router.preferred_flagship()
    tc = engine.ledger.cost_per_output(flagship, b.avg_input_tokens, b.avg_output_tokens)
    assert tc.fully_burdened_cpo == pytest.approx(
        tc.api_cost + tc.vector_db_cost + tc.amortized_capex + tc.maintenance_opex
    )


def test_router_routes_by_complexity():
    engine = make_engine()
    router: TokenOptimizerRouter = engine.router
    assert router.assess("Classify this ticket sentiment.", input_tokens=50) is TaskComplexity.SIMPLE
    assert router.assess("Analyze the root cause and design a mitigation strategy.", input_tokens=50) is TaskComplexity.COMPLEX
    # very long prompt is always complex
    assert router.assess("hi", input_tokens=9999) is TaskComplexity.COMPLEX


def test_router_picks_cheapest_fallback():
    engine = make_engine()
    fb = engine.router.cheapest_fallback()
    # ollama open llm is priced at 0 by default -> should win on cost
    assert fb.name == "ollama-open-llm"


def test_telemetry_ingestion_matches_sample():
    path = Path(__file__).resolve().parents[1] / "data" / "sample_telemetry.json"
    txns = json.loads(path.read_text())
    engine = make_engine()
    r = engine.from_telemetry(txns)
    assert r.detail["transactions_ingested"] == len(txns)
    assert r.price_source == "telemetry"
    # 1 flagged incident + 2 HITL reviews across 10 outputs
    assert r.detail["observed_incident_rate"] == pytest.approx(0.1)
    assert r.detail["observed_hitl_rate"] == pytest.approx(0.2)


def test_report_has_all_sections():
    r = make_engine().project()
    md = ExecutiveReport.render(r)
    for section in [
        "## Executive Summary",
        "## Unit Economics (CPO)",
        "## Risk-Adjusted Adjustments",
        "## Velocity & Throughput",
        "## Strategic Recommendation",
    ]:
        assert section in md


def test_cost_fetcher_falls_back_gracefully():
    fetcher = CostFetcher()
    engine = make_engine()
    price = fetcher.price_for(engine.config.flagships()[0])
    assert price.source in {"litellm", "default"}
    assert price.input_cost_per_token >= 0
