# AI ROI Calculator - Human vs AI + HITL

**Should you optimize the human process, or bring in AI with a human-in-the-loop?** This calculator answers that in money, after risk.

It prices every transaction three ways - **Human (as-is)**, **Human (optimized)**, and **AI + HITL** - deducts a *Hallucination Tax* for the expected cost of AI getting things wrong, projects the **break-even** on the AI build, and recommends **where to draw the human/AI line** given how sensitive the process is. Cost is one axis; a qualitative panel scores the rest (speed, consistency, auditability, compliance, CX, adaptability).

Two front ends over one shared model:

- **`dashboard/index.html`** - a self-contained, no-build **calculator**. Every input is a slider. Move one and the risk-adjusted P&L, the three-way cost comparison, the break-even chart, the recommended split, the qualitative verdict, and the executive report all recompute live. Open the file in any browser.
- **`roi_tracker`** - a zero-dependency Python engine for projections *and* real telemetry ingestion, with a one-page McKinsey-style executive report and the Human-vs-AI comparison.

## What it answers

1. **Human vs AI + HITL** - full cost per transaction and per month for all three operating models, cheapest flagged.
2. **Break-even projection** - cumulative cash of going AI (pay CapEx, save per txn) vs just optimizing the humans, month by month, with the payback point marked.
3. **Recommended approach** - "keep the most-sensitive X% human, move the remaining Y% to AI + HITL", driven by cost *and* process sensitivity.
4. **Process sensitivity + qualitative measures** - a sensitivity lever that shifts the split, plus seven Human-vs-AI quality dimensions and a composite AI-favorability score with a plain-English verdict.

---

## Quick start

```bash
# 1. Dashboard - just open it, no build step
open dashboard/index.html

# 2. Engine - forward projection from the baseline
PYTHONPATH=src python3 -m roi_tracker

# 3. Engine - ingest real telemetry, print the executive report
PYTHONPATH=src python3 -m roi_tracker --telemetry data/sample_telemetry.json --report

# 4. Override any variable from the CLI
PYTHONPATH=src python3 -m roi_tracker --legacy-cost 5.10 --volume 250000 --complex-share 0.4

# tests
pip install pytest && PYTHONPATH=src python3 -m pytest -q
```

Live token pricing (optional but recommended):

```bash
pip install litellm    # Dynamic Cost Fetcher then uses litellm's community pricing DB
```

Without `litellm`, the engine falls back to the editable default prices in `config.py` - it never hard-fails.

---

## The four modules

| Module | What it does |
|---|---|
| **Dynamic Cost Fetcher** (`cost_fetcher.py`) | Pulls current input/output token prices from `litellm`'s community pricing database (OpenAI, Anthropic, Google, ...). Falls back to declared defaults per model. |
| **Token Optimizer Agent** (`router.py`) | LLM-agnostic router. Reads cheap signals (length, intent keywords) to route *simple* tasks to the cheapest fallback model and *complex* tasks to a flagship - no LLM call, ~zero added cost. |
| **Micro-P&L Ledger** (`ledger.py`) | Computes **Fully Burdened Cost Per Output (CPO)** = API cost + vector-DB retrieval + amortized CapEx + maintenance OpEx, per transaction. |
| **Risk Pricer** (`risk_pricer.py`) | The **Hallucination Tax**: logs guardrail-flagged / human-in-the-loop outputs and deducts expected incident VaR + human remediation cost from gross ROI. |

`engine.py` composes them into a `ROIResult`; `report.py` renders the one-page executive brief.

---

## The pipeline (from the CFO interview)

Flagship (complex tasks): `claude-opus-4-8`, `gpt-5 / o-series`, `gemini-2.5-pro`
Fallback (simple tasks): `ollama` open LLM, `gpt-5-mini / 4o-mini`, `gemini-2.5-flash`

The router auto-selects the **cheapest** model in each tier from live prices. Change the roster in `config.py` (Python) or edit the price cells in the dashboard.

---

## Plain-English glossary

Every slider maps to a real financial term:

- **Legacy cost / txn** - what one transaction costs with humans today. The number AI must beat.
- **Fully Burdened CPO** - the true all-in AI cost per transaction, not just the API bill.
- **Hallucination Tax** - expected loss from catastrophic failures (incident rate x Value at Risk) plus human review cost. What risk costs you per transaction.
- **Amortized CapEx** - the one-time build spread across transactions. `CapEx / amortization volume`.
- **Break-even** - the monthly volume at which savings cover ongoing OpEx.
- **Net ROI** - net saving per dollar of AI run cost, after tax and OpEx.

---

## Executive report (Phase 3)

`ExecutiveReport.render()` emits exactly five sections: Executive Summary, Unit Economics (CPO), Risk-Adjusted Adjustments, Velocity & Throughput, Strategic Recommendation. The dashboard renders the same brief live and exports it as Markdown.

---

## Telemetry format

```json
[
  {"model": "claude-opus-4-8", "input_tokens": 2400, "output_tokens": 780,
   "sent_to_hitl": true, "remediation_cost": 8.0,
   "flagged_incident": false, "var_loss": 0}
]
```

Wire your production logs (or a `litellm` success/failure callback) into this shape to replace *assumed* incident/HITL rates with *measured* ones.

---

## Layout

```
src/roi_tracker/   engine + four modules + CLI
dashboard/         self-contained HTML calculator
data/              sample telemetry
tests/             pytest suite
reports/           generated reports (git-ignored by default)
```

## License

MIT. See [LICENSE](LICENSE).
