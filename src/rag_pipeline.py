"""
rag_pipeline.py — Layered-RAG verdict + (optional) real LLM call
===============================================================

WHAT THIS DOES (the heart of the system, revised per your insight)
-----------------------------------------------------------------
The knowledge base (data/corpus.json) has THREE layers, and the RAG verdict checks a
rumour against them:

  REGULATION layer (FIFA/UEFA) : transfer windows, release-clause enforceability,
                                 one-registration-per-season, FFP/PSR.
  CONTRACT   layer (club)      : each player's real release clause (termination fee) and
                                 free-agent status - i.e. salary/contract STRUCTURE.
  RECORD     layer (facts)     : confirmed past transfers (used to CONFIRM true rumours).

The verdict logic REFUTES as well as confirms:
  1. WINDOW check : a rumour dated outside the windows (e.g. "November") is INVALID
                    (grounded in REG01).
  2. CLAUSE check : if a rumour claims a fee BELOW the player's real release clause, or
                    claims a fee for a free agent, it is INCONSISTENT -> FALSE
                    (grounded in the contract doc). This is exactly your "€50m clause vs
                    €70m reality -> probably a rumour" example.
  3. RECORD check : if a retrieved record shows the same player+club CONFIRMED -> CONFIRMED;
                    if it shows the player STAYED -> FALSE.

This is what makes the system a real *filter*: it can shoot down false rumours using
authoritative knowledge, not just recognise ones that already happened.

TWO MODES (the single prompt-change point lives here)
-----------------------------------------------------
  MOCK (default, free) : the transparent consistency checker above.
  API  (OPENROUTER_API_KEY set, USE_MOCK != 1) : one prompt to the model, parsed to JSON.
  The prompt template below is the ONLY prompt in the system.

KEY FUNCTION
------------
- assess(rumor_text, layer1, retrieved, corpus_by_id, use_api=False, model=...) -> dict
"""

import json
import os
import re
import urllib.request

# FX to a common EUR basis for fee comparison (symbols AND words like EUR/GBP/USD).
FX_TO_EUR = {"€": 1.0, "£": 1.17, "$": 0.92,
             "eur": 1.0, "gbp": 1.17, "usd": 0.92}
VALID_WINDOW_MONTHS = {"june", "july", "august", "september", "january"}
INVALID_WINDOW_MONTHS = {
    "february", "march", "april", "may", "october", "november", "december"
}


def _parse_fee(text):
    """Return (amount_eur or None, is_free). Handles symbols (€/£/$) and words (EUR/GBP/USD).
    'm' / 'mn' / 'million' scales the amount by 1,000,000 so it is comparable to the
    release_clause_eur values in the corpus (which are stored in absolute euros)."""
    t = text.lower()
    if "free transfer" in t or "free agent" in t or "on a free" in t:
        return (0.0, True)
    m = re.search(r"(€|£|\$|eur|gbp|usd)\s?([\d]+(?:\.\d+)?)\s?(m|mn|million)?", t, re.IGNORECASE)
    if m:
        cur = m.group(1).lower()
        amt = float(m.group(2))
        if m.group(3):
            amt *= 1_000_000
        return (amt * FX_TO_EUR[cur], False)
    return (None, False)


def _claimed_month(text):
    t = text.lower()
    for mon in INVALID_WINDOW_MONTHS:
        if mon in t:
            return mon
    for mon in VALID_WINDOW_MONTHS:
        if mon in t:
            return mon
    return None


def player_in_text(player, text):
    """True if the corpus player is actually named in the text (full name, or surname of
    >= 4 chars). Used by the mock checker AND the anti-hallucination guard below."""
    if not player:
        return False
    t = text.lower()
    p = player.lower()
    if p in t:
        return True
    parts = p.split()
    return bool(parts) and len(parts[-1]) >= 4 and parts[-1] in t


def _grounding_guard(res, rumor_text, corpus_by_id):
    """Anti-hallucination guard (runs on BOTH mock and API results).

    A CONFIRMED/FALSE verdict must cite evidence that is about the RUMOURED player.
    Retrieval similarity (same club, same fee, same words) is NOT evidence. If every cited
    doc concerns a different player — e.g. rumour "Bruno Fernandes -> Bayern for GBP 100m"
    confirmed via Kane's record D03 — the verdict is downgraded to UNVERIFIED. REG* refs are
    player-independent by design and always pass.
    """
    if res.get("verdict") not in ("CONFIRMED", "FALSE") or not res.get("evidence"):
        return res
    for did in res["evidence"]:
        if did.startswith("REG"):
            return res
        doc = corpus_by_id.get(did, {})
        if player_in_text(doc.get("player"), rumor_text):
            return res
    bad = ", ".join(res["evidence"])
    return {
        "verdict": "UNVERIFIED", "confidence": 0.3, "evidence": [],
        "grounded": False, "mode": res.get("mode", "mock"),
        "reasoning": (f"Guard: cited evidence ({bad}) concerns other players; the rumoured "
                      f"player is not in the knowledge base, so the claim stays unverified."),
    }


def _call_openai(rumor_text, retrieved, corpus_by_id, model):
    """Real LLM path (zero-dependency urllib). Falls back to mock on any error."""
    context = "\n".join(
        f"[{did}] ({corpus_by_id[did].get('layer')}) "
        f"{corpus_by_id[did].get('player', corpus_by_id[did].get('title',''))}: "
        f"{corpus_by_id[did]['text']}"
        for did, _ in retrieved
    )
    # ===== THE SINGLE PROMPT TEMPLATE (edit here, exactly once, to test regressions) =====
    prompt = (
        "You verify football-transfer rumours against retrieved knowledge. Return strict JSON:\n"
        "{\"verdict\":\"CONFIRMED\"|\"FALSE\"|\"UNVERIFIED\",\"confidence\":0.0-1.0,"
        "\"evidence\":[doc_ids],\"reasoning\":str}.\n"
        "Rules: (1) A rumour dated outside the transfer windows is FALSE (cite REG01). "
        "(2) A rumour claiming a fee BELOW a player's release clause, or a fee for a free agent, "
        "is FALSE (cite the contract doc). (3) CONFIRMED only if a record doc names the SAME "
        "player as the rumour AND the destination club, with status CONFIRMED. (4) Matching only "
        "the club or the fee is NOT enough — retrieved docs about OTHER players are irrelevant "
        "context; if no retrieved doc names the rumoured player, return UNVERIFIED with empty "
        "evidence. Never invent evidence.\n\n"
        f"CONTEXT:\n{context}\n\nRUMOUR: {rumor_text}"
    )
    try:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/pe6201/football-rumor-filter",
                "X-Title": "Football Rumor Filter",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read().decode("utf-8"))
            parsed = json.loads(out["choices"][0]["message"]["content"])
            verdict = parsed.get("verdict", "UNVERIFIED")
            ev = parsed.get("evidence", [])
            return {
                "verdict": verdict, "confidence": float(parsed.get("confidence", 0.5)),
                "evidence": ev, "grounded": bool(ev) and verdict != "UNVERIFIED",
                "reasoning": parsed.get("reasoning", ""), "mode": "api",
                "usage": out.get("usage", {}),
            }
    except Exception as e:
        print(f"  [warn] API call failed ({e}); falling back to mock.")
        return _mock_assess(rumor_text, retrieved, corpus_by_id, None)


def _mock_assess(rumor_text, retrieved, corpus_by_id, layer1):
    """Conservative offline verdict via knowledge-base consistency checking."""
    claimed_eur, is_free = _parse_fee(rumor_text)
    mon = _claimed_month(rumor_text)
    mentioned = [
        d["player"].lower() for d in corpus_by_id.values()
        if d.get("player") and d["player"].lower() in rumor_text.lower()
    ]

    # (1) Transfer-window regulation: a rumour outside the windows is invalid.
    if mon and mon in INVALID_WINDOW_MONTHS:
        return {
            "verdict": "FALSE", "confidence": 0.9, "evidence": ["REG01"],
            "grounded": True,
            "reasoning": f"Rumour dated '{mon}' is outside the FIFA transfer windows (REG01).",
            "mode": "mock",
        }

    # (2) Release-clause / contract-structure check: refute fee inconsistencies.
    for pid in mentioned:
        for did, _ in retrieved:
            doc = corpus_by_id[did]
            if doc.get("layer") != "contract" or doc.get("player", "").lower() != pid:
                continue
            clause = doc.get("release_clause_eur", 0)
            if clause and clause > 0:
                if claimed_eur is not None and not is_free and claimed_eur < 0.9 * clause:
                    return {
                        "verdict": "FALSE", "confidence": 0.85, "evidence": [did],
                        "grounded": True,
                        "reasoning": (f"Claimed fee ~EUR {claimed_eur:,.0f} is below "
                                      f"{pid}'s release clause of EUR {clause:,.0f} ({did})."),
                        "mode": "mock",
                    }
                if is_free:
                    return {
                        "verdict": "FALSE", "confidence": 0.8, "evidence": [did],
                        "grounded": True,
                        "reasoning": f"{pid} has a release clause; cannot be a free transfer ({did}).",
                        "mode": "mock",
                    }
            elif clause == 0:  # free agent
                if claimed_eur is not None and claimed_eur > 0:
                    return {
                        "verdict": "FALSE", "confidence": 0.8, "evidence": [did],
                        "grounded": True,
                        "reasoning": f"{pid} is a free agent; a fee claim is inconsistent ({did}).",
                        "mode": "mock",
                    }

    # (3) Confirmed-record check.
    for pid in mentioned:
        for did, _ in retrieved:
            doc = corpus_by_id[did]
            if doc.get("layer") != "record" or doc.get("player", "").lower() != pid:
                continue
            if doc["status"] == "CONFIRMED" and doc["to_club"].lower() in rumor_text.lower():
                return {
                    "verdict": "CONFIRMED", "confidence": 0.9, "evidence": [did],
                    "grounded": True,
                    "reasoning": f"Retrieved {did} confirms {pid} -> {doc['to_club']}.",
                    "mode": "mock",
                }
            if doc["status"] == "STAYED" and doc["player"].lower() in rumor_text.lower():
                return {
                    "verdict": "FALSE", "confidence": 0.7, "evidence": [did],
                    "grounded": True,
                    "reasoning": f"Retrieved {did} shows {pid} stayed; rumored move is false.",
                    "mode": "mock",
                }

    return {
        "verdict": "UNVERIFIED", "confidence": 0.3, "evidence": [],
        "grounded": False,
        "reasoning": "No knowledge-base document supported or refuted this claim.",
        "mode": "mock",
    }


def assess(rumor_text, layer1, retrieved, corpus_by_id, use_api=False, model="gpt-4o-mini"):
    """Entry point. Routes to API (if configured) or mock consistency checker.
    Both paths then pass through the anti-hallucination grounding guard."""
    if use_api and os.environ.get("OPENROUTER_API_KEY") and os.environ.get("USE_MOCK") != "1":
        res = _call_openai(rumor_text, retrieved, corpus_by_id, model)
    else:
        res = _mock_assess(rumor_text, retrieved, corpus_by_id, layer1)
    return _grounding_guard(res, rumor_text, corpus_by_id)
