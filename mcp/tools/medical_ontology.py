"""Medical ontology MCP tools for the FHIR (Synthea) data lake.

Mirrors the CAUH ``medical_ontology`` module in shape but targets the FHIR
``condition`` table whose clinical codes are **SNOMED CT**. For each tool we
therefore match on a mix of
  - ``code_value``  — the SNOMED concept_id
  - ``code_display`` — the English label (regex-style ``RLIKE`` filter)

Three tools:

* ``expand_disease_term`` — natural-language (e.g. ``"diabetes"``) or SNOMED
  concept_id → list of anchor groups / SNOMED codes / ``sql_hints`` usable in
  a WHERE clause. The ``sql_hints`` target the ``condition`` table.

* ``get_disease_hierarchy`` — anchor key or SNOMED code → ICD-10 chapter/block
  context (label only), siblings in the same anchor, and rollup data usage.

* ``find_related_diseases`` — complications / comorbidities for a curated
  anchor. Complication groups carry either explicit SNOMED lists or ``RLIKE``
  patterns so we can fall back to text matching when the concept_id is not
  yet known to us.

All queries target the FHIR ``condition`` table (``code_value`` / ``code_display``
/ ``subject_reference``).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from emr_client import execute_sql
from metadata_loader import fqn

_ONTOLOGY_PATHS = [
    Path(__file__).resolve().parent.parent / "ontology" / "disease_ontology.yaml",
    Path(__file__).resolve().parent.parent.parent / "data" / "ontology" / "disease_ontology.yaml",
    Path("/var/task/ontology/disease_ontology.yaml"),
]

_MAX_MATCHES = 20


# ───────────────────────────── YAML loader ─────────────────────────────

@lru_cache(maxsize=1)
def _load_structure() -> dict:
    for p in _ONTOLOGY_PATHS:
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {"chapters": [], "disease_relations": []}


def _parse_range(rng: str) -> tuple[str, str]:
    lo, hi = rng.split("-", 1)
    return lo.strip(), hi.strip()


def _code_in_range(code3: str, rng: str) -> bool:
    if not code3 or len(code3) < 3:
        return False
    lo, hi = _parse_range(rng)
    return lo <= code3[:3].upper() <= hi


def _find_chapter(code3: str) -> dict | None:
    for ch in _load_structure().get("chapters", []) or []:
        if _code_in_range(code3, ch["range"]):
            return ch
    return None


def _find_block(code3: str) -> tuple[dict | None, dict | None]:
    ch = _find_chapter(code3)
    if not ch:
        return None, None
    for blk in ch.get("blocks", []) or []:
        if _code_in_range(code3, blk["range"]):
            return ch, blk
    return ch, None


def _sql_escape(s: str) -> str:
    return str(s).replace("'", "''")


def _in_list(vals: list[str]) -> str:
    return ",".join(f"'{_sql_escape(v)}'" for v in vals)


# ──────────────────────── Anchor matching helpers ────────────────────────

def _anchor_key(anchor: dict) -> str:
    return anchor.get("anchor") or anchor.get("label") or ""


def _anchor_display(anchor: dict) -> str:
    return f"{anchor.get('label', anchor.get('anchor','?'))} ({anchor.get('icd10','-')})"


def _match_anchors(query: str) -> list[dict]:
    """Find ``disease_relations`` entries that match the user's query.

    Matching order:
      1. Direct anchor key / label / Korean label substring
      2. Query contained in any of ``match_patterns`` (case-insensitive)
      3. Query equals one of ``snomed_codes``
      4. ICD-10 3-digit prefix inside the anchor's icd10 range (if numeric-like)
    """
    q = (query or "").strip()
    if not q:
        return []
    q_lower = q.lower()
    rels = _load_structure().get("disease_relations", []) or []
    hits: list[dict] = []
    for r in rels:
        fields = [r.get("anchor", ""), r.get("label", ""), r.get("label_ko", "")]
        if any(q == f for f in fields):
            hits.append(r); continue
        if any((f and (q_lower in str(f).lower() or str(f).lower() in q_lower)) for f in fields):
            hits.append(r); continue
        if q in (r.get("snomed_codes") or []):
            hits.append(r); continue
        for pat in r.get("match_patterns", []) or []:
            try:
                if re.search(pat, q_lower):
                    hits.append(r); break
            except re.error:
                continue
        else:
            # ICD-10 prefix fallback
            icd = r.get("icd10", "")
            if icd and q and q[0].isalpha() and q[1:2].isdigit():
                code3 = q[:3].upper()
                if "-" in icd:
                    lo, hi = _parse_range(icd)
                    if lo <= code3 <= hi:
                        hits.append(r)
    return hits


def _anchor_where_clause(anchor: dict) -> str:
    """Build a WHERE fragment that selects FHIR conditions belonging to
    this anchor (via SNOMED codes OR regex on display)."""
    parts: list[str] = []
    snomeds = anchor.get("snomed_codes") or []
    if snomeds:
        parts.append(f"`code_value` IN ({_in_list(snomeds)})")
    pats = anchor.get("match_patterns") or []
    for pat in pats:
        parts.append(f"LOWER(`code_display`) RLIKE '{_sql_escape(pat)}'")
    return " OR ".join(f"({p})" for p in parts) if parts else "1=0"


def _group_where_clause(group: dict) -> str:
    """Same as anchor_where_clause but for a complication / comorbidity
    sub-group."""
    parts: list[str] = []
    snomeds = group.get("snomed") or []
    if snomeds:
        parts.append(f"`code_value` IN ({_in_list(snomeds)})")
    pats = group.get("patterns") or []
    for pat in pats:
        parts.append(f"LOWER(`code_display`) RLIKE '{_sql_escape(pat)}'")
    return " OR ".join(f"({p})" for p in parts) if parts else "1=0"


def _count_group(where_clause: str) -> dict[str, int]:
    cond = fqn("condition")
    sql = (
        f"SELECT COUNT(DISTINCT `subject_reference`) AS pts, COUNT(*) AS rows_cnt "
        f"FROM {cond} WHERE {where_clause}"
    )
    rows = execute_sql(sql)
    if rows:
        r = rows[0]
        return {"patients": int(r.get("pts") or 0), "rows": int(r.get("rows_cnt") or 0)}
    return {"patients": 0, "rows": 0}


# ──────────────────────── Tool 1: expand_disease_term ────────────────────

def expand_disease_term(
    query: str,
    include_stats: bool = True,
    limit: int = 15,
) -> dict[str, Any]:
    """Expand a natural-language disease term into SNOMED codes for the FHIR
    ``condition`` table.

    Args:
        query: English term (``"diabetes"``), Korean term (``"당뇨병"``) or a
            SNOMED concept_id.
        include_stats: Attach patient counts per concept.
        limit: Maximum distinct concept_ids returned under ``discovered_concepts``.

    Returns:
        ``{query, matched_anchors[], discovered_concepts[], sql_hints, notes}``
    """
    if not query or not query.strip():
        return {"error": "query is required"}

    q = query.strip()
    anchors = _match_anchors(q)

    matched_out = []
    for a in anchors:
        entry = {
            "anchor": _anchor_key(a),
            "label": a.get("label"),
            "label_ko": a.get("label_ko"),
            "icd10": a.get("icd10"),
            "snomed_codes": a.get("snomed_codes") or [],
            "match_patterns": a.get("match_patterns") or [],
        }
        if include_stats:
            entry["data_usage"] = _count_group(_anchor_where_clause(a))
        matched_out.append(entry)

    # Discovered concepts: look up condition rows whose display matches the query
    discovered: list[dict] = []
    q_esc = _sql_escape(q)
    cond = fqn("condition")
    discover_sql = f"""
    SELECT `code_value` AS concept_id,
           MAX(`code_display`) AS display,
           COUNT(DISTINCT `subject_reference`) AS pts,
           COUNT(*) AS rows_cnt
    FROM {cond}
    WHERE LOWER(`code_display`) LIKE LOWER('%{q_esc}%')
       OR `code_value` = '{q_esc}'
    GROUP BY `code_value`
    ORDER BY pts DESC
    LIMIT {int(limit)}
    """
    for r in execute_sql(discover_sql):
        discovered.append({
            "concept_id": r.get("concept_id"),
            "display": r.get("display"),
            "data_usage": {
                "patients": int(r.get("pts") or 0),
                "rows":     int(r.get("rows_cnt") or 0),
            },
        })

    # SQL hints: anchors' WHERE + raw discovery fallback
    sql_hints: dict[str, str] = {}
    if anchors:
        clauses = [_anchor_where_clause(a) for a in anchors]
        sql_hints["primary_filter"] = " OR ".join(f"({c})" for c in clauses)
    if discovered:
        concept_ids = [d["concept_id"] for d in discovered if d.get("concept_id")]
        if concept_ids:
            sql_hints["discovered_concepts_in"] = (
                f"`code_value` IN ({_in_list(concept_ids)})"
            )

    return {
        "query": q,
        "matched_anchors": matched_out,
        "discovered_concepts": discovered,
        "sql_hints": sql_hints,
        "notes": (
            "matched_anchors 는 curated anchor 기반 (합병증·동반질환과 연계 가능). "
            "discovered_concepts 는 display 텍스트 매칭으로 찾은 SNOMED 코드 (raw 검색). "
            "condition 테이블의 WHERE 절에는 sql_hints.primary_filter 를 우선 사용."
        ),
    }


# ──────────────────────── Tool 2: get_disease_hierarchy ────────────────────

def get_disease_hierarchy(
    code_or_anchor: str,
    include_stats: bool = True,
) -> dict[str, Any]:
    """Return chapter/block context + siblings for an anchor or SNOMED code.

    Because the FHIR dataset lacks an explicit ICD-10 hierarchy on the
    concept rows, we resolve the input through the curated anchor first, then
    fall back to ICD-10 range information carried by the anchor.
    """
    if not code_or_anchor:
        return {"error": "code_or_anchor is required"}

    q = code_or_anchor.strip()
    anchors = _match_anchors(q)
    if not anchors:
        return {
            "query": q,
            "chapter": None,
            "block": None,
            "self": None,
            "siblings": [],
            "notes": "No matching curated anchor. Try expand_disease_term first.",
        }
    a = anchors[0]

    # ICD-10 chapter / block from the (shared) skeleton
    chapter_info = None
    block_info = None
    icd = a.get("icd10", "")
    if icd:
        lo, _ = _parse_range(icd) if "-" in icd else (icd[:3], icd[:3])
        ch, blk = _find_block(lo[:3])
        if ch:
            chapter_info = {
                "id":       ch.get("id"),
                "range":    ch["range"],
                "label_ko": ch.get("label_ko"),
                "label_en": ch.get("label_en"),
            }
        if blk:
            block_info = {
                "range":    blk["range"],
                "label_en": blk.get("label_en"),
            }

    siblings: list[dict] = []
    for other in _load_structure().get("disease_relations", []) or []:
        if _anchor_key(other) == _anchor_key(a):
            continue
        if other.get("icd10") and icd and other["icd10"].split("-")[0][:1] == icd.split("-")[0][:1]:
            # share the same letter (same ICD-10 chapter family)
            siblings.append({
                "anchor":   _anchor_key(other),
                "label":    other.get("label"),
                "label_ko": other.get("label_ko"),
                "icd10":    other.get("icd10"),
            })

    out = {
        "query": q,
        "chapter": chapter_info,
        "block": block_info,
        "self": {
            "anchor":       _anchor_key(a),
            "label":        a.get("label"),
            "label_ko":     a.get("label_ko"),
            "icd10":        a.get("icd10"),
            "snomed_codes": a.get("snomed_codes") or [],
        },
        "siblings": siblings,
    }
    if include_stats:
        out["stats_in_data"] = _count_group(_anchor_where_clause(a))
    return out


# ──────────────────────── Tool 3: find_related_diseases ────────────────────

def find_related_diseases(
    term_or_code: str,
    relation_type: str = "all",
    include_stats: bool = True,
) -> dict[str, Any]:
    """Return complications / comorbidities of a curated anchor.

    Args:
        term_or_code: English/Korean term, SNOMED concept_id, or anchor key.
        relation_type: ``all`` | ``complications`` | ``comorbidities``.
        include_stats: Attach patient counts from the ``condition`` table.
    """
    if not term_or_code or not term_or_code.strip():
        return {"error": "term_or_code is required"}

    anchors = _match_anchors(term_or_code)
    if not anchors:
        return {
            "anchor": term_or_code,
            "related": [],
            "notes": "No curated anchor. Try expand_disease_term first.",
        }
    a = anchors[0]
    related: list[dict] = []

    def add(group: dict, relation: str):
        entry = {
            "label":    group.get("label"),
            "label_ko": group.get("label_ko"),
            "relation": relation,
            "snomed":   group.get("snomed") or [],
            "patterns": group.get("patterns") or [],
        }
        if include_stats:
            entry["data_usage"] = _count_group(_group_where_clause(group))
        related.append(entry)

    if relation_type in ("all", "complications"):
        for g in a.get("complications") or []:
            add(g, "complication")
    if relation_type in ("all", "comorbidities"):
        for g in a.get("comorbidities") or []:
            add(g, "comorbidity")

    return {
        "anchor":   _anchor_display(a),
        "anchor_key": _anchor_key(a),
        "anchor_icd10": a.get("icd10"),
        "related": related,
    }
