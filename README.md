# Football Transfer Rumor Filter

A minimal, hand-built RAG system that checks football transfer rumours against a
three-layer authority knowledge base (league regulations · club release clauses ·
confirmed past transfers) and outputs an evidence-backed verdict:
**CONFIRMED / FALSE / UNVERIFIED**, with a PR action of **PUBLISH_GROUNDED** or
**HOLD**.

This README is for **running the code and viewing results**. The written report
is [`REPORT.md`](REPORT.md); the product/architecture doc is
[`PRODUCT.md`](PRODUCT.md); the evaluation doc is [`EVALS.md`](EVALS.md); the
data dictionary is [`data/README.md`](data/README.md).

---

## 1. Requirements

- Python 3.8+ (tested on 3.12).
- **No third-party package is required** to run the pipeline or the code demo —
  they use the Python standard library only and work fully offline (MOCK mode).
- Optional, only for the web demo (`demo_app.py`): `gradio` —
  `pip install -r requirements.txt`.
- Optional, only for the live-LLM path: an OpenRouter API key exported as
  `OPENROUTER_API_KEY`. **Not needed to grade this project** — the default
  MOCK mode is deterministic and free.

> Secrets are never committed. `.env` is git-ignored; the code reads it
> automatically if present, otherwise it falls back to MOCK.

---

## 2. Project structure

```
football-rumor-filter/
├── README.md                # this file (run & view results)
├── REPORT.md                # written report (≤1,200 words)
├── PRODUCT.md               # product / architecture doc
├── EVALS.md                 # evaluation doc
├── CHANGELOG.md
├── requirements.txt         # only gradio (for the web demo)
├── run_all.py               # end-to-end pipeline (console + JSON)
├── run_demo.py              # code-only demo (console table + JSON) — no web UI
├── demo_app.py              # bilingual Gradio web page (for the demo video)
├── .env.example             # template; copy to .env and fill key if you want live LLM
├── data/
│   ├── corpus.json          # 3-layer knowledge base (REG* / C* / D*, 28 docs)
│   ├── rumors.json          # 20 rumours + ground truth (system input)
│   ├── eval_set.json        # 10-case L1/L2 eval set
│   ├── demo_rumors.json     # 18 demo rumours (covers every verdict)
│   └── README.md            # data dictionary
├── src/
│   ├── retriever.py         # Layer 2 TF-IDF retrieval
│   ├── layer1_keyword_filter.py  # Layer 1 rule triage
│   ├── rag_pipeline.py      # Layer 3 verdict (MOCK + API) + grounding guard
│   ├── pr_alert.py          # PR action (PUBLISH_GROUNDED / HOLD)
│   ├── dual_bill.py         # cost model (retrieval offload)
│   ├── eval_harness.py      # L1/L2 evaluation
│   ├── run_all.py           # orchestrator
│   └── config.py            # .env loader (stdlib only)
└── outputs/                 # generated on each run (git-ignored)
    ├── alerts.json
    ├── summary.md
    └── demo_results.json
```

---

## 3. How to run

Open a terminal in the project root (`football-rumor-filter/`).

### A. Full pipeline (recommended first run)
```bash
python src/run_all.py
```
Runs all 20 rumours through the four stages, prints the required metric pair
(`share_filtered`, `escape_rate`), the L1/L2 eval, the dual-bill, and a retrieval
boundary demo, then writes `outputs/alerts.json` and `outputs/summary.md`.

### B. Code demo — console + JSON, no web page
```bash
python run_demo.py                         # data/demo_rumors.json, MOCK
python run_demo.py --input data/rumors.json
python run_demo.py --limit 5
python run_demo.py --out outputs/my_run.json
```
Prints a readable table (verdict / action / evidence / expected / match) to the
console and writes `outputs/demo_results.json`. Use this when you want to demo by
just running code in an IDE (PyCharm) — no browser needed.

### C. Web demo (for the recorded video)
```bash
pip install -r requirements.txt
python demo_app.py
```
Opens a bilingual (EN/中文) Gradio page: paste a rumour, click **Verify**, see
Layer-1 triage, retrieved docs, verdict, and the PR-alert JSON side by side.

---

## 4. MOCK vs live LLM

| Mode | How to enable | Notes |
|------|--------------|-------|
| **MOCK** (default) | no `OPENROUTER_API_KEY`, or `USE_MOCK=1` | offline, deterministic, free — use this for grading/demo |
| **API** | `OPENROUTER_API_KEY=sk-...` (and not `USE_MOCK=1`) | calls OpenRouter; non-deterministic, costs money |

Both paths share one prompt template, so behaviour is comparable.

---

## 5. Where to view results

- **Console** — every run prints verdicts, retrieved docs (with TF-IDF scores),
  and the metric pair.
- **`outputs/alerts.json`** — one grounded alert per rumour (verdict, evidence,
  action, reasoning, timestamp).
- **`outputs/summary.md`** — run summary with the metric pair.
- **`outputs/demo_results.json`** — when using `run_demo.py`.

---

## 6. Metrics reported (see `EVALS.md` for detail)

- **share_filtered** — fraction of rumours held (not published). On the 20-set:
  **50%**.
- **escape_rate** — false rumours wrongly CONFIRMED (the dangerous case):
  **0%**.
- **L1 accuracy** (label) and **L2 faithfulness** (grounded in a retrieved doc):
  **100%** on the 10-case eval set.

The two filtering numbers are always reported **together**, because reporting
only one can hide a failure mode.

> All figures above are from the **default MOCK run (no API key)**. To reproduce
> them exactly, run without `OPENROUTER_API_KEY` (or `USE_MOCK=1`):
> `python src/run_all.py`. With a live key the LLM may shift a borderline case
> (e.g. one true rumour held as UNVERIFIED) — see `EVALS.md` / `REPORT.md` §3.

---

## 7. Quick architecture

```
rumour ─▶ Layer 1 rule triage ─▶ Layer 2 TF-IDF retrieval ─▶ Layer 3 verdict
                                                              (MOCK checker
                                                               or OpenRouter LLM)
                                                            └▶ grounding guard
                                                                 (anti cross-player
                                                                  hallucination)
        └────────────────────────────▶ PR action: PUBLISH_GROUNDED / HOLD
```

External intelligence = the OpenRouter LLM plus the TF-IDF retrieval "tool".
Full box diagram in [`PRODUCT.md`](PRODUCT.md).

---

## 8. Notes for graders

- The project runs and is reproducible **without any API key** (MOCK mode).
- Knowledge base is small and English-only by design (see `Rough edges` in
  `REPORT.md`); out-of-base players correctly return UNVERIFIED.
- To change the LLM behaviour, edit **the single prompt template** in
  `src/rag_pipeline.py` and re-run — do not hand-tune per case.
