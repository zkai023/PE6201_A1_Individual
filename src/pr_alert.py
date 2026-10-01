"""
pr_alert.py — Grounded PR alert generator (Layer 3 output)
===========================================================

WHAT THIS DOES
--------------
Converts a RAG verdict into a single, structured PR alert object. This is the artefact a
communications team would actually consume. Crucially it carries a `grounded` flag and the
`evidence` doc_ids, so a FALSE or UNVERIFIED alert can NEVER be published as fact without a
human sign-off. This is the L2-faithfulness guarantee made concrete.

KEY FUNCTION
------------
- build_alert(rumor_id, rumor_text, rag_result) -> dict
"""

from datetime import datetime, timezone


def build_alert(rumor_id, rumor_text, rag_result):
    """
    Wrap a RAG verdict into a publishable / hold-able alert.

    The `action` field encodes the operational decision:
      PUBLISH_GROUNDED  -> verified by corpus, safe to use in comms
      HOLD              -> not grounded; must get human verification first
    """
    verdict = rag_result["verdict"]
    grounded = rag_result.get("grounded", False)

    if verdict == "CONFIRMED" and grounded:
        action = "PUBLISH_GROUNDED"
    else:
        action = "HOLD"

    return {
        "rumor_id": rumor_id,
        "rumor": rumor_text,
        "verdict": verdict,
        "confidence": rag_result.get("confidence"),
        "grounded": grounded,
        "evidence": rag_result.get("evidence", []),
        "reasoning": rag_result.get("reasoning", ""),
        "action": action,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "caution": (
            "Grounded in retrieved corpus; safe to use in comms."
            if action == "PUBLISH_GROUNDED"
            else "UNVERIFIED or ungrounded — require human sign-off before any PR action."
        ),
    }
