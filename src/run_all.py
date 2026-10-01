"""
run_all.py — End-to-end orchestrator (clone the repo and just run this)
========================================================================

WHAT THIS DOES
--------------
1. Loads the LAYERED knowledge base (regulation + contract + record), the 20 rumours, and
   the 10-case eval set.
2. Builds the TF-IDF retrieval index.
3. Runs every rumour through Layer-1 triage -> retrieve -> Layered-RAG assess -> PR alert.
4. Computes the professor's REQUIRED PAIR of metrics: escape rate + share_filtered.
5. Prints the dual bill (proposed system vs all-LLM baseline) — measured cost.
6. Runs the L1/L2 eval harness.
7. Demonstrates the retrieval boundary with one out-of-corpus rumour.
8. Writes outputs/alerts.json and outputs/summary.md.

HOW TO RUN
----------
    cd football-rumor-filter
    python src/run_all.py                 # offline mock mode (default, free)
    USE_MOCK=0 OPENROUTER_API_KEY=sk-or-v1-... python src/run_all.py   # real LLM on the 20 rumours

No external packages required; pure Python standard library.
"""

import sys
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from config import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))  # auto-read .env at repo root (optional; MOCK default if absent)

from retriever import load_corpus, build_index, retrieve
from layer1_keyword_filter import filter_rumor
from rag_pipeline import assess
from pr_alert import build_alert
from dual_bill import run_system_bill, run_baseline_bill, print_bills
from eval_harness import evaluate

USE_API = False


def _load(name):
    with open(os.path.join(ROOT, "data", name), "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    global USE_API
    USE_API = bool(os.environ.get("OPENROUTER_API_KEY")) and os.environ.get("USE_MOCK") != "1"

    corpus = load_corpus(os.path.join(ROOT, "data", "corpus.json"))
    corpus_by_id = {d["doc_id"]: d for d in corpus}
    rumors = _load("rumors.json")["rumors"]
    eval_set = _load("eval_set.json")

    vecs, idf = build_index(corpus)

    def retrieve_fn(text, top_k=3):
        return retrieve(text, vecs, idf, top_k)

    # ---- Step 3: full pipeline over all 20 rumours ----
    alerts = []
    false_total = 0
    false_confirmed = 0
    for r in rumors:
        layer1 = filter_rumor(r["text"])
        retrieved = retrieve_fn(r["text"])
        res = assess(r["text"], layer1, retrieved, corpus_by_id, USE_API)
        alert = build_alert(r["rumor_id"], r["text"], res)
        alerts.append(alert)
        if r["ground_truth"] == "FALSE":
            false_total += 1
            if res["verdict"] == "CONFIRMED":
                false_confirmed += 1

    # ---- Step 4: the REQUIRED PAIR of metrics ----
    # share_filtered = fraction of rumours NOT safe to publish (HOLD) = real filtering rate.
    share_filtered = sum(1 for a in alerts if a["action"] != "PUBLISH_GROUNDED") / len(alerts)
    # escape_rate = FALSE rumours wrongly CONFIRMED (the dangerous failure mode).
    escape_rate = (false_confirmed / false_total) if false_total else 0.0

    # ---- Step 5: dual bill (retrieval offload) ----
    system_bill = run_system_bill(rumors, filter_rumor, retrieve_fn, corpus_by_id, USE_API)
    baseline_bill = run_baseline_bill(rumors, corpus, USE_API)
    print_bills(system_bill, baseline_bill)

    # ---- Step 6: L1/L2 eval ----
    ev = evaluate(eval_set, filter_rumor, retrieve_fn, assess, corpus_by_id, USE_API)
    print("\n" + "=" * 64)
    print("L1/L2 EVALUATION (10 cases)")
    print("=" * 64)
    for c in ev["per_case"]:
        flag = "OK " if (c["l1_ok"] and c["l2_ok"]) else "XX "
        print(f"{flag}{c['case_id']} {c['rumor_id']}: L1 {c['pred_l1']}"
              f"(exp {c['expected_l1']}) | grounded={c['pred_grounded']}"
              f"(exp {c['expected_grounded']}) | ev={c['evidence']}")
    print(f"\nL1 accuracy     : {ev['l1_accuracy']*100:.0f}%")
    print(f"L2 faithfulness : {ev['l2_faithfulness']*100:.0f}%")

    # ---- Step 4 (printed): pair ----
    print("\n" + "=" * 64)
    print("REQUIRED METRIC PAIR (report together, never alone)")
    print("=" * 64)
    print(f"share_filtered (rumours NOT published / held) : {share_filtered*100:.0f}%")
    print(f"escape_rate  (FALSE rumours wrongly CONFIRMED) : {escape_rate*100:.0f}%")
    print("=" * 64)

    # ---- Step 7: retrieval boundary demo (player absent from knowledge base) ----
    print("\nRETRIEVAL BOUNDARY DEMO (player absent from knowledge base):")
    ooc = "Pedri is close to a surprise move to Manchester United for GBP 50m."
    layer1 = filter_rumor(ooc)
    retrieved = retrieve_fn(ooc)
    res = assess(ooc, layer1, retrieved, corpus_by_id, USE_API)
    print(f"  top retrieved: {retrieved}")
    print(f"  verdict: {res['verdict']} | grounded: {res['grounded']} | "
          f"reasoning: {res['reasoning']}")

    # ---- Step 8: write outputs ----
    os.makedirs(os.path.join(ROOT, "outputs"), exist_ok=True)
    with open(os.path.join(ROOT, "outputs", "alerts.json"), "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

    summary = [
        "# Run Summary",
        "",
        f"- Mode: {'API' if USE_API else 'MOCK (offline)'}",
        f"- Rumours processed: {len(rumors)}",
        f"- Alerts PUBLISH_GROUNDED: {sum(1 for a in alerts if a['action']=='PUBLISH_GROUNDED')}",
        f"- Alerts on HOLD: {sum(1 for a in alerts if a['action']=='HOLD')}",
        f"- share_filtered: {share_filtered*100:.0f}%",
        f"- escape_rate: {escape_rate*100:.0f}%",
        f"- L1 accuracy: {ev['l1_accuracy']*100:.0f}%",
        f"- L2 faithfulness: {ev['l2_faithfulness']*100:.0f}%",
        f"- System est. input tokens: {system_bill['in_tokens']} vs baseline {baseline_bill['in_tokens']}",
        "",
        "## Sample alerts",
        "",
        "```json",
        json.dumps(alerts[:3], ensure_ascii=False, indent=2),
        "```",
    ]
    with open(os.path.join(ROOT, "outputs", "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary))

    print("\n[done] wrote outputs/alerts.json and outputs/summary.md")


if __name__ == "__main__":
    main()
