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
    "sandhigatavata",
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
