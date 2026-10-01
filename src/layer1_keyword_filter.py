"""
layer1_keyword_filter.py — Layer 1 rule-based triage (the RULE BASELINE)
========================================================================

WHAT THIS DOES
--------------
Before any (paid) LLM call, every rumour passes through a transparent keyword rule that
scores its *source credibility*. This is the honest, free, non-ML baseline the professor's
DATA feedback asked for (you only have ~20 labelled rumours - not enough to train a classifier).

Decisions
---------
  PASS_TO_RAG     -> credible wording (e.g. "completed", "signs", "release clause") -> send to RAG
  LOW_CONFIDENCE  -> hedged / unverifiable wording (e.g. "cousin", "rumour has it") ->
                     still sent to RAG but flagged for human review

KEY POINT (changed per your insight): Layer 1 no longer tries to *hard-block* false rumours.
The real filtering now happens in the Layered RAG (rag_pipeline.py), which REFUTES rumours
by checking them against release clauses and transfer regulations. Layer 1 is only a cheap
cost/confidence triage.

KEY FUNCTION
------------
- filter_rumor(text) -> dict {decision, score, signals}
"""

CREDIBLE_SIGNALS = [
    "romano", "ornstein", "official", "here we go", "medical", "fee agreed",
    "club-to-club", "agreement", "confirmed", "done deal", "release clause",
    "registered", "completed", "signs", "joins", "triggered",
]

SUSPECT_SIGNALS = [
    "cousin", "i heard", "rumour has it", "maybe", "perhaps", "speculation",
    "clickbait", "my source", "trust me", "could potentially", "unconfirmed reports",
    "grows", "want to", "close to", "in talks", "set to", "pushing for",
]


def filter_rumor(text):
    """
    Score a rumour's source credibility with keyword rules.

    Returns dict {decision, score, signals}.
      decision: 'PASS_TO_RAG' (score>=1) or 'LOW_CONFIDENCE' (otherwise)
    """
    t = text.lower()
    score = 0
    signals = []

    for kw in CREDIBLE_SIGNALS:
        if kw in t:
            score += 1
            signals.append(("+", kw))
    for kw in SUSPECT_SIGNALS:
        if kw in t:
            score -= 1
            signals.append(("-", kw))

    decision = "PASS_TO_RAG" if score >= 1 else "LOW_CONFIDENCE"
    return {"decision": decision, "score": score, "signals": signals}
