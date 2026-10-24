"""Memory retrieval without a model: BM25 over what the brain has stored locally.

The corpus is built fresh on each query from files the brain already keeps, so there is no
index to go stale: finished episodes (prompt and deliverable), adopted lessons, the mind's
long-term memory, and any text the operator drops into `notes/`. A query that matches
nothing says so; it never makes an answer up.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass

from .home import Home, read_jsonl

_STOP = frozenset(
    "a an and are as at be by did do does for from had has have i in is it its me my of on or "
    "our so that the their them there this to was we were what when where which who why will "
    "with you your about know recall remember search memory".split()
)
NOTE_SUFFIXES = (".md", ".txt")


def _stem(w: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP]


@dataclass
class Doc:
    source: str  # a path relative to the brain home, or a lesson id
    text: str


@dataclass
class Hit:
    source: str
    score: float
    snippet: str


def _read(p) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def corpus(home: Home) -> list[Doc]:
    docs: list[Doc] = []
    if home.episodes.is_dir():
        for d in sorted(home.episodes.iterdir()):
            if '"route": "recall"' in _read(d / "route.json"):
                continue  # an earlier answer from memory is not a new memory
            parts = [(d / f).read_text(encoding="utf-8", errors="replace")
                     for f in ("prompt.md", "deliverable.md") if (d / f).is_file()]
            if parts:
                docs.append(Doc(f"episodes/{d.name}", "\n".join(parts)))
    for row in read_jsonl(home.root / "lessons.jsonl"):
        docs.append(Doc(f"lessons.jsonl#{row.get('id', '?')}", json.dumps(row)))
    ltm = home.mind_current / "LongTermMEMORY.md"
    if ltm.is_file():
        docs.append(Doc("mind/current/LongTermMEMORY.md", ltm.read_text(encoding="utf-8")))
    notes = home.root / "notes"
    if notes.is_dir():
        for p in sorted(notes.rglob("*")):
            if p.suffix in NOTE_SUFFIXES and p.is_file():
                docs.append(Doc(str(p.relative_to(home.root)), p.read_text(encoding="utf-8", errors="replace")))
    return docs


def bm25(query: str, docs: list[Doc], *, k: int = 5, k1: float = 1.5, b: float = 0.75) -> list[Hit]:
    q = set(tokens(query))
    if not q or not docs:
        return []
    toks = [tokens(d.text) for d in docs]
    avg = sum(map(len, toks)) / len(toks) or 1.0
    df = Counter(t for ts in toks for t in set(ts))
    n = len(docs)
    hits = []
    for d, ts in zip(docs, toks):
        tf = Counter(ts)
        score = 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(ts) / avg))
        if score > 0:
            hits.append(Hit(d.source, round(score, 3), _snippet(d.text, q)))
    return sorted(hits, key=lambda h: -h.score)[:k]


def _snippet(text: str, q: set[str]) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    best = max(lines, key=lambda ln: len(q & set(tokens(ln))), default="")
    return best[:240]


def search(home: Home, query: str, *, k: int = 5) -> list[Hit]:
    return bm25(query, corpus(home), k=k)


# A prompt that asks the brain what it already knows is answered from memory, not by a model.
RECALL_PROMPT = re.compile(
    r"^\s*(?:recall|search (?:my |your )?memory(?: for)?|what do (?:you|i|we) know about|"
    r"what did (?:you|i|we) (?:find|learn|decide|record) about)\b[:\s]*(?P<q>.+)",
    re.I | re.S,
)


def recall_query(prompt: str) -> str | None:
    m = RECALL_PROMPT.match(prompt)
    return m.group("q").strip(" ?.") if m else None


def render(query: str, hits: list[Hit]) -> str:
    if not hits:
        return (f"TL;DR: I have nothing recorded about {query!r}.\n\nThis is a gap in what I have "
                "stored, not an outage: no episode, lesson, memory or note matches.\n")
    lines = [f"TL;DR: {len(hits)} local record(s) match {query!r} (retrieved by BM25, no model).", ""]
    lines += [f"- `{h.source}` (score {h.score}): {h.snippet}" for h in hits]
    return "\n".join(lines) + "\n"
