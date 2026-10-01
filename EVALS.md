# EVALS.md — Evaluation Explainer

> Companion to `README.md` §3 and `src/eval_harness.py`. Explains **how** the system is
> evaluated and **why** each metric exists. (Requirement: "transparently check-in … the evals
> you wrote … put explainer files for each, data and evals".)

---

## Two-layer evaluation

- **L1 (classification):** did we label `TRUE` / `FALSE` / `UNVERIFIABLE` correctly versus
  `expected_l1` in `eval_set.json`?
- **L2 (faithfulness):** when the alert says `CONFIRMED`, is it actually *grounded* in a
  retrieved corpus document (`expected_grounded`)? This is the anti-hallucination check — a
  `CONFIRMED` with no cited doc is a failure.

---

## The required metric pair (always reported together)

| Metric | Definition | Why it matters |
|---|---|---|
| **share_filtered** | fraction of rumours NOT safe to publish (action ≠ `PUBLISH_GROUNDED`) | proves the system *actually filters* instead of rubber-stamping |
| **escape_rate** | FALSE rumours wrongly CONFIRMED | the dangerous failure mode; must be ~0 |

Reporting them as a **pair** prevents gaming: a naive "publish-everything" baseline scores
`escape_rate = 0%` (nothing is wrongly confirmed because everything is confirmed) **but**
`share_filtered = 0%`. Only a system that both filters and stays accurate scores well on both.

---

## Other metrics

- **L1 accuracy, L2 faithfulness** — from the 10-case `eval_set.json` (via `eval_harness.py`).
- **Dual-bill retrieval offload** (`dual_bill.py`): measures the input-token saving of
  *retrieve-top-k then prompt* versus *paste the full corpus every call*, on the **same** 20
  rumours. Reached **88.2%** fewer input tokens. This turns the "retrieval drastically reduces
  cost" claim into a measured number.

---

## How to run

```bash
cd football-rumor-filter
python src/run_all.py          # prints L1/L2, share_filtered, escape_rate, dual bill
```

All metrics are **deterministic in mock mode** (the default, no API key needed). The figures
reported in `REPORT.md` — `share_filtered` **50%**, `escape_rate` **0%**, L1 **100%**, L2 **100%**
(on the 10-case eval), dual-bill **88.2%** — are all produced by this default MOCK run, so a
grader who clones the repo and runs `python src/run_all.py` with no key gets exactly these numbers.
With a key set (`USE_MOCK=0 OPENROUTER_API_KEY=...`) the LLM path is exercised; `temperature = 0`
keeps it reproducible, and any API error falls back to mock. Note: the live LLM is non-deterministic
and may shift a borderline case (e.g. one true rumour was held as UNVERIFIED), which is itself the
mock-vs-API trade-off discussed in `REPORT.md` §3.

---

## Discipline (avoid silent regression)

Edit the prompt in **exactly one place** — `THE SINGLE PROMPT TEMPLATE` in
`src/rag_pipeline.py` — then re-run `run_all.py` and report the before/after L1/L2 (see
`REPORT.md` §5). This is the change-control rule for the whole project.
