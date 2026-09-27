"""Clinician review ledger interface (Graph B).

Machine-readable record of every Ayurvedic term / history item proposed in
``docs/ayurvedic/``: what it means, which wording is accepted, which
patient-language variants are recognized, whether it is required history,
its source, and — critically — its review standing.

Standing values: "provisional" (source-derived, awaiting clinician) or
"reviewed" (a named clinician signed it with a date). NOTHING in the
ledger is reviewed until the clinician packet sign-off is transcribed here.
Code must treat "provisional" as: usable as intake features/guidance, never
as validated clinical labels.
"""
import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

_LEDGER_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "clinical_review_ledger.json")

# Correlates the ledger + packet 6.C explicitly contest. These must never
# appear as authoritative labels in patient- or doctor-facing output until a
# clinician resolves them. (Input-side symptom matching is unaffected.)
CONTESTED_CORRELATES = [
    "amlapitta",
    "agnimandya",
    "grahani",
    "amavata",
    "sandhigata vata",
    "grudhrasi",
    "vatarakta",
    "tamaka shwasa",
    "tamaka",
    "kshayaja",
    "rajayakshma",
]


@lru_cache(maxsize=1)
def load_ledger(path: Optional[str] = None) -> Dict[str, Any]:
    with open(path or _LEDGER_PATH, encoding="utf-8") as f:
        return json.load(f)


def ledger_items() -> List[Dict[str, Any]]:
    return load_ledger().get("items", [])


def get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    for item in ledger_items():
        if item.get("id") == entry_id:
            return item
    return None


def is_reviewed(entry_id: str) -> bool:
    """True only with an explicit reviewer + date sign-off. Nothing is."""
    entry = get_entry(entry_id)
    if not entry or entry.get("review_status") != "reviewed":
        return False
    return bool(entry.get("reviewer") and entry.get("review_date"))


def is_patient_usable(term: str) -> bool:
    """Whether a classical term may appear patient-facing as a label.

    Contested correlates are never patient-usable without clinician review;
    plain-language feature descriptions are unaffected (they are not labels).
    """
    lowered = (term or "").strip().lower()
    return not any(c in lowered for c in CONTESTED_CORRELATES)


def required_history(domain: str) -> List[Dict[str, Any]]:
    """Required history items for a pilot domain (constrain completeness, not order)."""
    prefix = {"digestive": "H-GI-", "musculoskeletal": "H-MS-", "respiratory": "H-RS-"}
    pre = prefix.get(domain or "")
    if not pre:
        return []
    return [i for i in ledger_items() if i.get("id", "").startswith(pre) and i.get("required")]


def reviewed_count() -> int:
    return sum(1 for i in ledger_items() if is_reviewed(i.get("id", "")))


# ---------------------------------------------------------------------------
# Graph G: clinician review import contract.
# ---------------------------------------------------------------------------
# A future real review moves PROVISIONAL -> CONFIRMED / REJECTED / REVISED
# through apply_review() on a ledger mapping. It validates the minimum
# record the packet requires (decision + reviewer + date) and returns a NEW
# mapping; the shipped ledger file is never mutated implicitly. No fake
# values are populated anywhere in this repository.

REVIEW_DECISIONS = ("CONFIRMED", "REJECTED", "REVISED")

# Packet-native decision codes (clinician_review_results_v1.md §1–§4 tables use
# Keep/Modify/Remove; §2.4-style combination questions may be Deferred).
# Deterministic transcription map — the packet wording is preserved, the
# stored decision is normalized. DEFERRED never confirms anything.
PACKET_DECISIONS = {
    "Keep": "CONFIRMED",
    "Modify": "REVISED",
    "Remove": "REJECTED",
    "Defer": "DEFERRED",
}

# Questionnaire §5 usability rulings. Orthogonal to confirmation: a term can
# be clinically recognized yet banned from patient-facing use.
USABILITY = ("patient-usable", "physician-only", "banned")
# Packet §5 checkbox codes.
USABILITY_CODES = {"P": "patient-usable", "M": "physician-only", "N": "banned"}


def apply_review(
    ledger: Dict[str, Any],
    entry_id: str,
    *,
    decision: str,
    reviewer: str,
    date: str,
    notes: str = "",
    final_wording: str = "",
    usability: Optional[str] = None,
    required: Optional[bool] = None,
) -> Dict[str, Any]:
    """Record one clinician decision, returning an updated ledger copy.

    `decision` accepts code decisions (CONFIRMED/REJECTED/REVISED) or
    packet-native codes (Keep/Modify/Remove/Defer). `usability` accepts
    §5 codes (P/M/N) or full values; it is recorded only and has no runtime
    effect until a later, explicitly reviewed runtime change. `required`
    transcribes the packet M/O column. Raises ValueError when the record is
    incomplete. The caller's mapping is not mutated.
    """
    normalized = PACKET_DECISIONS.get(decision, decision)
    if normalized not in REVIEW_DECISIONS + ("DEFERRED",):
        raise ValueError(f"decision must be one of {list(PACKET_DECISIONS) + list(REVIEW_DECISIONS)}")
    usability_value = None
    if usability is not None:
        usability_value = USABILITY_CODES.get(usability, usability)
        if usability_value not in USABILITY:
            raise ValueError(f"usability must be one of {list(USABILITY_CODES) + list(USABILITY)}")
    if not (reviewer or "").strip():
        raise ValueError("reviewer identity is required; no anonymous sign-off")
    if not (date or "").strip():
        raise ValueError("review date is required")
    items = [dict(i) for i in ledger.get("items", [])]
    for item in items:
        if item.get("id") == entry_id:
            # Only an explicit CONFIRMED counts as reviewed; everything else
            # (including DEFERRED) stays provisional and never confirms.
            item["review_status"] = "reviewed" if normalized == "CONFIRMED" else "provisional"
            item["review_decision"] = normalized
            item["reviewer"] = reviewer.strip()
            item["review_date"] = date.strip()
            if notes:
                item["notes"] = ((item.get("notes") or "") + f" | Review: {notes}").strip(" |")
            if final_wording:
                item["accepted_terminology"] = final_wording
            if usability_value is not None:
                item["usability"] = usability_value
            if required is not None:
                item["required"] = bool(required)
            return {**ledger, "items": items}
    raise ValueError(f"unknown ledger entry: {entry_id}")


def transcribe_packet_row(
    ledger: Dict[str, Any],
    entry_id: str,
    *,
    code: str,
    reviewer: str,
    date: str,
    rationale: str = "",
    final_wording: str = "",
    usability_code: Optional[str] = None,
    mandatory: Optional[bool] = None,
) -> Dict[str, Any]:
    """Deterministic transcription of one packet table row (Graphs C/D).

    Maps the packet's own columns (K/M/R + M/O + §5 P/M/N) onto apply_review
    without reinterpreting clinical content: rationale becomes the note,
    final wording amends accepted terminology, nothing else is inferred.
    """
    if code not in PACKET_DECISIONS:
        raise ValueError(f"code must be one of {list(PACKET_DECISIONS)}")
    return apply_review(
        ledger, entry_id, decision=code, reviewer=reviewer, date=date,
        notes=rationale, final_wording=final_wording,
        usability=usability_code, required=mandatory,
    )


# ---------------------------------------------------------------------------
# Graphs C/E: clinical term mentions in a session (status visibility).
# ---------------------------------------------------------------------------
# Distinct dimensions, never mixed:
#   concept_provenance[concept].source  -> HOW the value was obtained
#                                          (llm | heuristic | patient_raw | clinician-entered)
#   clinical_mentions[].status          -> WHAT clinicians have said about
#                                          the term (reviewed | provisional)
# source=llm + status=provisional is the normal, honest combination.

_MENTION_MIN_LEN = 3


def _mention_terms() -> List[Dict[str, Any]]:
    terms = []
    for item in ledger_items():
        concept = (item.get("concept") or "").strip()
        if len(concept) >= _MENTION_MIN_LEN:
            terms.append({"term": concept, "id": item.get("id", ""),
                          "status": item.get("review_status", "provisional")})
    return terms


def clinical_mentions(session_like: Any) -> List[Dict[str, Any]]:
    """Ledger terms appearing in patient text (Graph C/E transparency).

    Scans raw answers, chief complaint, and collected values for whole-word
    mentions of ledger concepts and reports each term's review standing, so
    doctor-facing views can show WHAT was said alongside WHETHER clinicians
    have validated the term. Generic intake vocabulary is unaffected.
    """
    import re

    texts: List[str] = []
    for raw in getattr(session_like, "raw_answers", []) or []:
        if isinstance(raw, dict) and raw.get("answer"):
            texts.append(str(raw["answer"]))
    if getattr(session_like, "chief_complaint", None):
        texts.append(str(session_like.chief_complaint))
    for v in (getattr(session_like, "collected_concepts", {}) or {}).values():
        if v:
            texts.append(str(v) if not isinstance(v, list) else " ".join(map(str, v)))
    blob = "\n".join(texts)
    if not blob.strip():
        return []
    seen = set()
    out = []
    try:
        terms = _mention_terms()
    except Exception:
        return []  # ledger unreadable: views stay alive, safety never depends on this
    for t in terms:
        if t["id"] in seen:
            continue
        if re.search(r"\b" + re.escape(t["term"]) + r"\b", blob, re.IGNORECASE):
            seen.add(t["id"])
            out.append({"term": t["term"], "entry_id": t["id"], "status": t["status"]})
    return out
