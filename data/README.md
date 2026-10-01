# data/ — Dataset Explainer

> Companion to `README.md` §2. This file explains **every** dataset so the evaluator can
> understand exactly what was used to build and test the demo. (Requirement: "transparently
> check-in the data you used … put explainer files for each, data and evals".)

---

## `corpus.json` — the three-layer authority knowledge base (RAG retrieval corpus)

- **Size:** 28 documents — 4 regulation (`REG*`), 11 contract (`C*`), 13 record (`D*`).
- **Realism:** all are real events / real rules. Sources: FIFA transfer regulations,
  BBC Sport, Sky Sports, Marca, L'Équipe, club contract filings.
- **Key fields:**
  - `layer` — `regulation` | `contract` | `record`
  - `player` — the player the doc is about (empty for `REG*`)
  - `release_clause_eur` — the player's real release clause in absolute EUR; `0` = free agent
  - `status` — `CONFIRMED` | `STAYED` (record layer only)
  - `to_club` / `from_club` — clubs involved
  - `text` — the retrievable sentence(s)
  - `source` — where the fact came from
- **Role:** the *only* authority the system may cite. A verdict with no matching doc stays
  `UNVERIFIED`. Add a doc to expand knowledge; delete `C01` to demo the retrieval boundary
  (see `README.md` §5).

---

## `rumors.json` — 20 production rumours (system input)

- **R01–R10** later came **TRUE** in real life.
- **R11–R20** are written to **conflict** with the corpus (wrong fee / wrong window / wrong
  status) on purpose, to test whether the system can *refute* them.
- Field `ground_truth`: `TRUE` | `FALSE`. Used by `run_all.py` to compute `escape_rate`.
- This is the set fed to `run_all.py` for the batch demonstration.

---

## `eval_set.json` — 10-case L1/L2 evaluation set (with gold answers)

- Fields per case: `expected_l1` (`TRUE_RUMOR` / `FALSE_RUMOR` / `UNVERIFIABLE`),
  `expected_grounded` (bool), `expected_evidence` (doc_ids).
- This is the **only** set where the prompt may be changed *once* and re-run to check
  regression (see `README.md` §8 and `EVALS.md`).
- It validates all four decision paths: confirm-by-record, refute-by-clause, refute-by-window,
  and honest UNVERIFIED.

---

## `demo_rumors.json` — 18 demo-only rumours

- **Independent** of the 20 production rumours. Each carries `expected{verdict, evidence,
  action, note}`, `category`, and `label`.
- **Purpose:** during the video demo you copy any one line and paste it into the Demo input
  box (the UI has no dropdown / built-in library). Covers every verdict / action / grounded
  branch so the demo is reproducible.
- **Not** used by `run_all.py` (batch mode uses `rumors.json` + `eval_set.json`).
