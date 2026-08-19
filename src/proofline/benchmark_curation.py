"""Retrieval-blind quality curation for generated benchmark candidate pools.

Curation may reject questions that are obviously headings/procedural fragments, but it must not
consult retrieval results. The raw generated pool should remain available as experiment evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .hashing import sha256_text

_CURATION_METHOD = "proofline-retrieval-benchmark-curation/v1"
_MONTHS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may",
    "jun", "june", "jul", "july", "aug", "august", "sep", "sept", "september",
    "oct", "october", "nov", "november", "dec", "december",
}
_BOILERPLATE = {
    "agenda", "meeting", "open", "posted", "regular", "special", "minutes",
    "req", "request", "leg", "legislation", "for", "purch", "purchase",
    "enter", "necessary", "agmts", "agreement", "agreements", "support", "plans",
    "ordinance", "resolution", "approve", "approval", "authorizing", "authorize",
}
_GENERIC_START = {
    "agenda", "meeting", "posted", "regular", "special", "req", "request",
    "enter", "support", "ordinance", "resolution", "approve", "approval",
}
_METADATA_TERMS = {"ordinance", "resolution"}
_GENERIC_INSTITUTIONAL_PHRASES = {
    "the building code",
    "building code fund",
}
_PROJECT_TERMS = {
    "project", "water", "main", "replacement", "improvement", "bridge", "street",
    "road", "sewer", "park", "avenue", "ave", "building", "facility",
}


def _tokens(value: str) -> list[str]:
    return [token.strip(".,:;()[]{}\"'").casefold() for token in value.split() if token.strip()]


def lexical_phrase_quality(query: str) -> tuple[tuple[int, int, int, int] | None, str | None]:
    """Return a deterministic quality tuple or a rejection reason.

    Rules use only the query string. They do not inspect search results, target rank, or scores.
    """
    raw_tokens = [token for token in query.split() if token]
    tokens = _tokens(query)
    normalized = " ".join(tokens)
    if len(tokens) < 2:
        return None, "too_short"
    if tokens[0] in _GENERIC_START:
        return None, "generic_heading_start"
    if any(token in _MONTHS for token in tokens):
        return None, "calendar_heading"
    if any(token in _METADATA_TERMS for token in tokens):
        return None, "record_metadata_fragment"
    if normalized in _GENERIC_INSTITUTIONAL_PHRASES:
        return None, "generic_institutional_heading"
    boilerplate_count = sum(token in _BOILERPLATE for token in tokens)
    if boilerplate_count >= 2:
        return None, "procedural_boilerplate"

    alphabetic = [token for token in raw_tokens if any(char.isalpha() for char in token)]
    all_upper = bool(alphabetic) and all(token.upper() == token for token in alphabetic)
    projectish = any(token in _PROJECT_TERMS for token in tokens)
    if all_upper and not projectish:
        return None, "all_caps_fragment"

    has_natural_case = any(any(char.islower() for char in token) for token in raw_tokens)
    long_tokens = sum(len(token) >= 5 for token in tokens)
    quality = (
        1 if has_natural_case else 0,
        1 if projectish else 0,
        long_tokens,
        sum(len(token) for token in tokens),
    )
    return quality, None


def curate_benchmark_pool(pool: dict, *, max_per_kind: int = 6) -> dict:
    if pool.get("schema") != "proofline-retrieval-eval/v2":
        raise ValueError("benchmark pool must use proofline-retrieval-eval/v2")
    selection = pool.get("selection") or {}
    if selection.get("retrieval_results_consulted") is not False:
        raise ValueError("cannot curate a pool that consulted retrieval results")
    if max_per_kind < 1:
        raise ValueError("max_per_kind must be positive")

    buckets: dict[str, list[dict]] = defaultdict(list)
    rejected: list[dict] = []
    for original in pool.get("cases") or []:
        case = dict(original)
        kind = str(case.get("selection_kind") or "unknown")
        if kind.startswith("lexical_entity_"):
            quality, reason = lexical_phrase_quality(str(case.get("query") or ""))
            if quality is None:
                rejected.append(
                    {
                        "case_id": case.get("case_id"),
                        "query": case.get("query"),
                        "selection_kind": kind,
                        "reason": reason,
                    }
                )
                continue
            case["selection_quality"] = list(quality)
        buckets[kind].append(case)

    selected: list[dict] = []
    for kind in sorted(buckets):
        rows = buckets[kind]
        if kind == "negative_control":
            chosen = sorted(rows, key=lambda item: item["case_id"])
        elif kind.startswith("lexical_entity_"):
            chosen = sorted(
                rows,
                key=lambda item: (
                    tuple(-value for value in item["selection_quality"]),
                    sha256_text(str(item.get("query", "")).casefold()),
                ),
            )[:max_per_kind]
        else:
            chosen = sorted(rows, key=lambda item: sha256_text(item["case_id"]))[:max_per_kind]
        selected.extend(chosen)

    kind_counts = Counter(str(case.get("selection_kind")) for case in selected)
    rejection_counts = Counter(str(item.get("reason")) for item in rejected)
    return {
        "schema": pool["schema"],
        "name": pool.get("name", "Proofline R1 retrieval benchmark") + " — curated",
        "selection": {
            "method": _CURATION_METHOD,
            "upstream_method": selection.get("method"),
            "retrieval_results_consulted": False,
            "raw_case_count": len(pool.get("cases") or []),
            "curated_case_count": len(selected),
            "max_per_kind": max_per_kind,
            "kind_counts": dict(sorted(kind_counts.items())),
            "rejection_counts": dict(sorted(rejection_counts.items())),
            "rejected_lexical_cases": rejected,
            "note": (
                "Question-quality curation uses query text only. No retrieval results, rankings, "
                "or scores are consulted before the suite is frozen."
            ),
        },
        "cases": selected,
    }
