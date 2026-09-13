"""Manual correction path shared by patient (P06) and doctor routers.

Preserves the original AI-derived extraction and provenance — the original
value is snapshotted once (on the first manual correction) and provider,
confidence, and raw_result are never overwritten.
"""
from typing import Any, Optional

from backend.models.schema import Session, DocumentField


def correct_document(
    session: Session,
    index: int,
    corrected_value: Optional[str] = None,
    strength: Optional[str] = None,
    dose: Optional[str] = None,
    frequency: Optional[str] = None,
) -> DocumentField:
    if index < 0 or index >= len(session.documents):
        raise IndexError("Document index out of range")
    doc = session.documents[index]

    if not doc.manually_corrected:
        # Audit snapshot of the original AI-derived extraction, taken once on the
        # first manual correction. provider/confidence/raw_result are also never
        # overwritten below, so the full provenance stays intact.
        doc.original_extraction = {
            "medicine": doc.extracted_value,
            "strength": doc.strength,
            "dose": doc.dose,
            "frequency": doc.frequency,
            "confidence": doc.confidence,
            "provider": doc.provider,
        }

    if corrected_value is not None:
        doc.extracted_value = corrected_value
    if strength is not None:
        doc.strength = strength
    if dose is not None:
        doc.dose = dose
    if frequency is not None:
        doc.frequency = frequency

    # Manual correction satisfies the review gate (spec Section 6: a document is
    # clear when confidence >= 0.5 OR a manual correction has been applied).
    doc.needs_review = False
    doc.manually_corrected = True
    return doc