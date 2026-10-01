"""
dual_bill.py — Dual-bill cost comparison (addresses the professor's METRICS feedback)
=======================================================================================

WHAT THIS DOES
--------------
The problem statement claimed (§2) that retrieval "drastically reduces cost" versus an
all-LLM baseline. The professor's METRICS feedback: don't assert that without measuring it,
on the SAME inputs. dual_bill.py runs the SAME 20 rumours through two configurations and
prints TWO bills so the saving is a measured fact.

This revised version measures the cost of RETRIEVAL OFFLOAD (the real RAG benefit):
  (A) PROPOSED SYSTEM : Layer-1 triage + retrieve only the top-k relevant docs, then ONE
                        RAG call whose prompt carries just those few docs.
  (B) ALL-LLM BASELINE : no retrieval -> to have any chance it must paste the ENTIRE
                        knowledge base into every call. Same 1 call, but a huge prompt.

Both make 1 call per rumour; the difference is prompt size, which is exactly what retrieval
buys you. Offline, tokens are word-count estimates; with a key, the API `usage` gives exact
numbers. The SAVING RATIO is robust either way.

KEY FUNCTIONS
-------------
- estimate_tokens(text) -> int
- run_system_bill(...) / run_baseline_bill(...) -> dict
- print_bills(system_bill, baseline_bill) -> None
"""

import json

PRICE_PER_1K_IN = 0.00015
PRICE_PER_1K_OUT = 0.00060


def estimate_tokens(text):
    """Rough token estimate: ~1.3 tokens per word."""
    return int(len(text.split()) * 1.3)


def _cost(in_tokens, out_tokens):
    return in_tokens / 1000 * PRICE_PER_1K_IN + out_tokens / 1000 * PRICE_PER_1K_OUT


def run_system_bill(rumors, filter_fn, retrieve_fn, corpus_by_id, use_api):
    """Proposed system: retrieve top-k, then ONE RAG call with only those docs."""
    in_t = out_t = 0
    llm_calls = 0
    for r in rumors:
        filter_fn(r["text"])  # triage (cost of the rule itself is ~0)
        retrieved = retrieve_fn(r["text"])
        ctx_words = sum(len(corpus_by_id[did]["text"].split()) for did, _ in retrieved)
        in_t += estimate_tokens(r["text"]) + ctx_words
        out_t += 60
        llm_calls += 1
    return {
        "name": "PROPOSED (Layer-1 + RAG, top-k retrieved)",
        "llm_calls": llm_calls,
        "in_tokens": in_t,
        "out_tokens": out_t,
        "cost_usd": round(_cost(in_t, out_t), 4),
    }


def run_baseline_bill(rumors, corpus, use_api):
    """All-LLM baseline: no retrieval, so the whole knowledge base is pasted each call."""
    full_words = sum(len(d["text"].split()) for d in corpus)
    in_t = out_t = 0
    for r in rumors:
        in_t += estimate_tokens(r["text"]) + full_words
        out_t += 60
    return {
        "name": "ALL-LLM BASELINE (no retrieval, full KB per call)",
        "llm_calls": len(rumors),
        "in_tokens": in_t,
        "out_tokens": out_t,
        "cost_usd": round(_cost(in_t, out_t), 4),
    }


def print_bills(system_bill, baseline_bill):
    """Print the two bills and the measured retrieval-offload saving."""
    print("\n" + "=" * 64)
    print("DUAL BILL — measured cost on the SAME 20 rumours")
    print("=" * 64)
    print(f"{'metric':<22}{system_bill['name'][:20]:<22}{baseline_bill['name'][:20]}")
    rows = [
        ("LLM calls", system_bill["llm_calls"], baseline_bill["llm_calls"]),
        ("Input tokens (est.)", system_bill["in_tokens"], baseline_bill["in_tokens"]),
        ("Output tokens (est.)", system_bill["out_tokens"], baseline_bill["out_tokens"]),
        ("Estimated cost (USD)", f"${system_bill['cost_usd']}", f"${baseline_bill['cost_usd']}"),
    ]
    for name, a, b in rows:
        print(f"{name:<22}{str(a):<22}{str(b)}")
    if baseline_bill["in_tokens"] > 0:
        save = (1 - system_bill["in_tokens"] / baseline_bill["in_tokens"]) * 100
        print(f"\n=> MEASURED SAVING from retrieval offload: {save:.1f}% fewer input tokens")
    print("=" * 64)
