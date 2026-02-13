from __future__ import annotations

import re

try:
    # RapidFuzz is C++-accelerated and is suitable for large choice lists.
    # https://github.com/rapidfuzz/RapidFuzz
    import rapidfuzz as _rapidfuzz  # type: ignore
    from rapidfuzz import fuzz, process, utils  # type: ignore
except Exception:  # pragma: no cover
    _rapidfuzz = None
    fuzz = None
    process = None
    utils = None


_NORM_RE = re.compile(r"[^a-z0-9]+")


def norm(s: str) -> str:
    return _NORM_RE.sub(" ", (s or "").lower()).strip()


def search_backend_info() -> str:
    """
    Human-readable backend identifier, useful for UI/debugging.
    """
    if process is None or fuzz is None or utils is None:
        return "fallback"
    try:
        v = getattr(_rapidfuzz, "__version__", "") if _rapidfuzz is not None else ""
    except Exception:
        v = ""
    return f"RapidFuzz {v}".strip() if v else "RapidFuzz"


def search_hits_by_lib(
    *,
    q: str,
    bases_all: list[str],
    bases_lc: list[str],
    bases_lib: list[str],
    descr_cache: dict[str, str],
    max_total: int = 800,
) -> tuple[str, dict[str, list[str]], bool, int, dict[str, float]]:
    """
    Search using RapidFuzz (fast fuzzy matching).

    Returns (q, hits_by_lib, truncated, shown) where hits_by_lib[lib] is sorted best-first.
    """
    q_raw = (q or "").strip()
    if not q_raw:
        return (q, {}, False, 0, {})

    qn = norm(q_raw)
    qtoks = [t for t in qn.split() if t]
    if not qtoks:
        return (q, {}, False, 0, {})

    # If RapidFuzz isn't available, fall back to strict substring filtering to avoid crashes.
    if process is None or fuzz is None or utils is None:
        hits: dict[str, list[str]] = {}
        lib_best: dict[str, float] = {}
        shown = 0
        for i, base in enumerate(bases_all):
            if shown >= max_total:
                break
            d = descr_cache.get(base) or ""
            hay = (base + " " + d).lower()
            ok = True
            for t in qtoks:
                if t not in hay:
                    ok = False
                    break
            if not ok:
                continue
            lib = bases_lib[i]
            hits.setdefault(lib, []).append(base)
            lib_best[lib] = max(lib_best.get(lib, 0.0), 1.0)
            shown += 1
        return (q, hits, shown >= max_total, shown, lib_best)

    # Build choice strings aligned by index, so RapidFuzz can return indices.
    # Search should use both base name and description.
    # Small prefilter: if we can quickly narrow candidates by raw token presence,
    # RapidFuzz will have far fewer choices to score.
    cand_indices: list[int] | None = None
    if len(bases_all) >= 5000 and qtoks:
        cand: list[int] = []
        for i, base in enumerate(bases_all):
            d = descr_cache.get(base) or ""
            hay = bases_lc[i] if i < len(bases_lc) else base.lower()
            if d:
                hay = hay + " " + d.lower()
            ok = True
            for t in qtoks:
                if t not in hay:
                    ok = False
                    break
            if ok:
                cand.append(i)
            # Avoid huge intermediate lists for very broad queries.
            if len(cand) > 20000:
                cand = []
                break
        if cand:
            cand_indices = cand

    idxs = cand_indices if cand_indices is not None else list(range(len(bases_all)))

    choices: list[str] = []
    for i in idxs:
        base = bases_all[i]
        d = descr_cache.get(base) or ""
        choices.append(base if not d else (base + " " + d))

    # Pull more than max_total then post-filter by tokens to ensure all tokens are present.
    limit = min(len(choices), max_total * 6)
    matches = process.extract(
        q_raw,
        choices,
        scorer=fuzz.WRatio,
        processor=utils.default_process,
        limit=limit,
    )

    # Token gate (after RapidFuzz) to ensure multi-token queries like "0402 1005"
    # don't return partial matches.
    want = [t for t in utils.default_process(q_raw).split() if t]
    scored: dict[str, list[tuple[float, str]]] = {}
    lib_best: dict[str, float] = {}
    shown = 0
    for _choice, score, idx in matches:
        if shown >= max_total:
            break
        try:
            orig_i = idxs[int(idx)]
            base = bases_all[orig_i]
        except Exception:
            continue
        hay = choices[int(idx)]
        hay_p = utils.default_process(hay)
        if want and any(t not in hay_p for t in want):
            continue
        lib = bases_lib[orig_i]
        s = float(score)

        scored.setdefault(lib, []).append((s, base))
        lib_best[lib] = max(lib_best.get(lib, 0.0), s)
        shown += 1

    hits: dict[str, list[str]] = {}
    for lib, items in scored.items():
        items.sort(key=lambda x: (-x[0], x[1].lower()))
        hits[lib] = [b for _s, b in items]

    truncated = shown >= max_total and len(matches) >= limit
    return (q, hits, truncated, shown, lib_best)

