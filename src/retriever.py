"""
retriever.py — Minimal, hand-built RAG retriever (Layer 2 retrieval stage)
==========================================================================

WHAT THIS DOES
--------------
Given a corpus of real football-transfer documents (data/corpus.json) it builds a
TF-IDF index and, for any query (a rumour), returns the top-k most similar documents
together with their cosine similarity scores. This is the "retrieval" half of the
minimal RAG system required by the assignment: no external embedding API, fully
deterministic, runs offline with the Python standard library only.

WHY TF-IDF AND NOT A NEURAL EMBEDDER
------------------------------------
The Foundations / End-of-Course brief rewards *hand-building* the competing approach and
measuring it. A transparent lexical retriever is easy to diagnose (you can see exactly
which terms matched), which is exactly what the professor's "intentionally break it to
find the retrieval boundary" instruction asks for. It also means the whole pipeline runs
with zero dependencies and zero cost.

KEY FUNCTIONS
-------------
- load_corpus(path)            -> list[dict]   load the JSON corpus
- build_index(docs)            -> (vecs, idf)  pre-compute TF-IDF vectors for every doc
- retrieve(query, vecs, idf, top_k=3) -> list[(doc_id, score)]
"""

import json
import math
import re
from collections import Counter


def _tokenize(text):
    """Lower-case, keep alphanumerics only. 'real-madrid' -> ['real','madrid']."""
    return re.findall(r"[a-z0-9]+", text.lower())


def load_corpus(path):
    """Load data/corpus.json -> list of document dicts."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_index(docs):
    """
    Build length-normalised TF-IDF vectors for every document.

    Returns
    -------
    vecs : dict  doc_id -> {term: weight}   (cosine-ready, unit length)
    idf  : dict  term    -> idf weight      (re-used for query terms)
    """
    df = Counter()
    tokenised = {}
    for d in docs:
        toks = set(_tokenize(d["text"]))
        tokenised[d["doc_id"]] = toks
        df.update(toks)

    n = len(docs)
    # smoothed idf
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    vecs = {}
    for d in docs:
        tf = Counter(_tokenize(d["text"]))
        vec = {}
        length_sq = 0.0
        for t, c in tf.items():
            w = (1.0 + math.log(c)) * idf.get(t, 1.0)
            vec[t] = w
            length_sq += w * w
        norm = math.sqrt(length_sq) or 1.0
        vecs[d["doc_id"]] = {t: v / norm for t, v in vec.items()}

    return vecs, idf


def retrieve(query, vecs, idf, top_k=3):
    """
    Cosine-similarity search of `query` against pre-built `vecs`.

    Returns a list of (doc_id, score) sorted by descending score, length = top_k.
    A score near 0.0 means the corpus contains essentially nothing relevant — which is
    exactly the signal the pipeline uses to flag a rumour as UNVERIFIED / potentially
    FALSE (the retrieval "boundary" the professor wants you to find).
    """
    q_tf = Counter(_tokenize(query))
    q_vec = {}
    q_len_sq = 0.0
    for t, c in q_tf.items():
        w = (1.0 + math.log(c)) * idf.get(t, 1.0)
        q_vec[t] = w
        q_len_sq += w * w
    q_norm = math.sqrt(q_len_sq) or 1.0

    scores = []
    for doc_id, vec in vecs.items():
        dot = 0.0
        for t, w in q_vec.items():
            if t in vec:
                dot += w * vec[t]
        scores.append((doc_id, dot / q_norm))

    scores.sort(key=lambda x: -x[1])
    return [(did, round(s, 4)) for did, s in scores[:top_k]]
