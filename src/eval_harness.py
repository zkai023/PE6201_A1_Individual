"""
eval_harness.py — L1/L2 dual-layer evaluation (the prompt-eval part)
=====================================================================

WHAT THIS DOES
--------------
Runs the 10-case eval_set.json through the full pipeline and scores it on TWO layers, as
required by the brief:

  L1 (classification) : did we label TRUE / FALSE / UNVERIFIABLE correctly?
  L2 (faithfulness)   : when the alert says CONFIRMED, is it actually grounded in a
                        retrieved corpus doc? (no hallucination)

It prints per-case results and aggregate rates. NOTE: we change the prompt in
rag_pipeline.py EXACTLY ONCE and re-run this harness to report regressions — that is the
discipline the assignment asks for.

KEY FUNCTION
------------
- evaluate(eval_set, filter_fn, retrieve_fn, assess_fn, corpus_by_id, use_api) -> dict
"""

_VERDICT_TO_L1 = {
    "CONFIRMED": "TRUE_RUMOR",
    "FALSE": "FALSE_RUMOR",
    "UNVERIFIED": "UNVERIFIABLE",
}


def evaluate(eval_set, filter_fn, retrieve_fn, assess_fn, corpus_by_id, use_api):
    total = len(eval_set["cases"])
    l1_correct = 0
    l2_faithful = 0
    per_case = []

    for c in eval_set["cases"]:
        layer1 = filter_fn(c["rumor"])
        retrieved = retrieve_fn(c["rumor"])
        res = assess_fn(c["rumor"], layer1, retrieved, corpus_by_id, use_api)

        pred_l1 = _VERDICT_TO_L1[res["verdict"]]
        l1_ok = pred_l1 == c["expected_l1"]
        l2_ok = (res.get("grounded", False) == c["expected_grounded"])
        l1_correct += l1_ok
        l2_faithful += l2_ok

        per_case.append({
            "case_id": c["case_id"],
            "rumor_id": c["rumor_id"],
            "expected_l1": c["expected_l1"],
            "pred_l1": pred_l1,
            "l1_ok": l1_ok,
            "expected_grounded": c["expected_grounded"],
            "pred_grounded": res.get("grounded", False),
            "l2_ok": l2_ok,
            "verdict": res["verdict"],
            "evidence": res.get("evidence", []),
        })

    return {
        "total": total,
        "l1_accuracy": l1_correct / total,
        "l2_faithfulness": l2_faithful / total,
        "per_case": per_case,
    }
