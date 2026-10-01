# Changelog — Football Transfer Rumor Filter

## [1.0.0] — 2026-10-01 (submission build)
- Layered-RAG pipeline: regulation (REG*), contract / release-clause (C*), confirmed-record (D*) knowledge base.
- Layer 1 rule-based source-credibility triage (no ML; transparent keyword baseline).
- Layer 2 hand-built TF-IDF retrieval (standard library only, fully interpretable).
- Layer 3 consistency checker (offline MOCK) + optional OpenRouter LLM path; single prompt template.
- Grounding guard: downgrades CONFIRMED/FALSE whose evidence concerns a different player (anti cross-player hallucination).
- PR-alert layer: PUBLISH_GROUNDED vs HOLD, with grounded citation.
- Dual-bill cost model: retrieval offload cuts ~88.2% of input tokens vs all-LLM baseline.
- Eval harness (L1 label accuracy + L2 faithfulness) and required metric pair (share_filtered + escape_rate).
- `run_all.py`: one-command end-to-end run (console + outputs/alerts.json, outputs/summary.md).
- `run_demo.py`: code-only demo (console table + outputs/demo_results.json), no web UI needed.
- `demo_app.py`: bilingual Gradio web page for the recorded demo video.
- Deliverable docs: README (this repo), REPORT, PRODUCT, EVALS, data/README.

## [0.9.0] — 2026-09 (earlier milestones)
- Problem Statement submitted (Milestone 1).
- Initial 20-rumour set + 10-case eval set.
- First RAG prototype (news-corpus flavour), later refactored into the layered authority knowledge base per course feedback.
