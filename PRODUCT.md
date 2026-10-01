# PRODUCT.md — Football Transfer Rumor Filter

> Product documentation for the PE6201 End-of-Course Project. Companion to `README.md`
> (code & data guide) and `REPORT.md` (written report). This file satisfies the
> "Code Repo → Product Documentation" requirement: Persona, Input, Output, high-level
> product Architecture, and Metrics targetted vs reached.

---

## 1. Persona (who is the user)

**Primary user:** a football club's **Communications / PR officer** (or a journalist
fact-checking desk). They receive a continuous stream of transfer rumours and must decide —
quickly and with evidence — whether to **publish, hold, or debunk** each one.

**Job to be done:** replace manual, inconsistent vetting with an auditable, evidence-linked
decision. Every output carries the exact authority it rests on, so a human can trust or
override it in one glance.

---

## 2. Input

A single **free-text transfer rumour**. Example:

> "Barcelona wonderkid Gavi is set to join Manchester United for GBP 80m this summer."

In batch mode each rumour may carry a `rumor_id`. The system never requires structured
fields — plain language is the input.

---

## 3. Output

A structured **PR alert** (JSON) with:

| Field | Meaning |
|---|---|
| `verdict` | `CONFIRMED` \| `FALSE` \| `UNVERIFIED` |
| `action` | `PUBLISH_GROUNDED` (safe to publish) \| `HOLD` (needs human sign-off) |
| `grounded` | bool — is the verdict backed by a corpus document? |
| `evidence` | list of cited doc_ids (`REG*` / `C*` / `D*`) |
| `reasoning` | human-readable explanation |
| `confidence` | 0–1 |

The `HOLD` action is the safety net: `FALSE` and `UNVERIFIED` (and any ungrounded
`CONFIRMED`) are never auto-published.

---

## 4. High-level Product Architecture (box diagram)

How an input transforms into an output through the code logic and the external
intelligence (LLM + Tools):

```
                         ┌──────────────────────────────────────────────────────┐
   INPUT (rumour text) ─►│  Layer 1  Rule-based source-credibility triage        │
                         │  (layer1_keyword_filter.py)  — free, no LLM           │
                         │  → PASS_TO_RAG / LOW_CONFIDENCE                        │
                         └───────────────────────┬──────────────────────────────┘
                                                 ▼
                         ┌──────────────────────────────────────────────────────┐
                         │  Layer 2  RETRIEVER (TOOL)  — TF-IDF vector search     │
                         │  (retriever.py)  pulls Top-k docs from 3-layer KB      │
                         │  EXTERNAL TOOL: knowledge base (data/corpus.json)      │
                         └───────────────────────┬──────────────────────────────┘
                                                 ▼
                         ┌──────────────────────────────────────────────────────┐
                         │  Layer 3  RAG VERDICT  (rag_pipeline.py)               │
                         │   ├─ MOCK: offline consistency checker (default, free) │
                         │   └─ API : ONE prompt to EXTERNAL LLM (OpenRouter) ◄──┤
                         │        (THE SINGLE PROMPT TEMPLATE)                     │
                         │  → {verdict, confidence, grounded, evidence, reasoning}│
                         │  → anti-hallucination GROUNDING GUARD (both modes)      │
                         └───────────────────────┬──────────────────────────────┘
                                                 ▼
                         ┌──────────────────────────────────────────────────────┐
                         │  Layer 4  PR ALERT  (pr_alert.py)                      │
                         │  → PUBLISH_GROUNDED / HOLD  (the OUTPUT above)         │
                         └──────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                    OUTPUT (grounded PR alert JSON)
```

**External intelligence called out explicitly:**
- **LLM (OpenRouter):** used only in API mode; receives the retrieved context + rumour as a
  single prompt and returns strictly-parsed JSON. Falls back to mock on any error.
- **Tools:** the TF-IDF retriever and the three-layer knowledge base — the system's
  retrieval capability, kept separate from the generative model so cost and reasoning are
  measurable.

---

## 5. Metrics — Targetted vs Reached

| Metric | Target (design intent) | Reached (measured, `run_all.py`) |
|---|---|---|
| L1 classification accuracy | ≥ 0.90 | **1.00** |
| L2 faithfulness (no hallucinated publish) | 1.00 | **1.00** |
| escape_rate (false rumour wrongly CONFIRMED) | ≤ 0.00 | **0.00** |
| share_filtered (system actually filters, not pass-all) | > 0.00 | **0.50*** |
| retrieval offload saving vs all-LLM baseline | measurable > 0 | **88.2%** fewer input tokens |

\* `share_filtered = 0.50` on the balanced 20-rumour eval set (10 true / 10 false by
construction); it demonstrates the system *distinguishes* rather than rubber-stamping
everything. A naive "publish-all" baseline would score `share_filtered = 0%` and
`escape_rate = 0%` — which is why the two are always reported as a pair.

---

## 6. Code map (see `README.md` for the full tree)

- `src/retriever.py` — Layer 2 retrieval (hand-built TF-IDF)
- `src/layer1_keyword_filter.py` — Layer 1 rule triage
- `src/rag_pipeline.py` — Layer 3 verdict (mock + API + grounding guard)
- `src/pr_alert.py` — Layer 4 grounded alert
- `src/dual_bill.py` — measured retrieval-offload cost
- `src/eval_harness.py` — L1/L2 evaluation
- `src/run_all.py` — end-to-end orchestrator
- `src/config.py` — `.env` loader (zero-config for the evaluator)
- Data: `data/corpus.json`, `data/rumors.json`, `data/eval_set.json`, `data/demo_rumors.json`
- Explainer files: `data/README.md` (data), `EVALS.md` (evaluation)
