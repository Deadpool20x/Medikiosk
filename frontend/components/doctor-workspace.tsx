"use client";

import { useState } from "react";
import { Button, Card, ConfidenceIndicator, EmptyState, FieldLabel, Input, StateNotice, StatusBadge, Textarea } from "./ui";
import { Icon } from "./icons";

type View = "list" | "detail" | "document";

const cases = [
  { id: "MK-DEMO-1042", patient: "Demo patient", complaint: "Headache and fever", time: "Today · 10:32", status: "Review needed" },
  { id: "MK-DEMO-1041", patient: "Demo patient", complaint: "Persistent cough", time: "Today · 09:18", status: "Ready for review" },
  { id: "MK-DEMO-1040", patient: "Demo patient", complaint: "Back pain", time: "Yesterday · 16:40", status: "Confirmed" },
];

export function DoctorWorkspace() {
  const [view, setView] = useState<View>("list");
  const [confirmed, setConfirmed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [complaint, setComplaint] = useState("Headache and fever since yesterday");
  const [search, setSearch] = useState("");
  const filtered = cases.filter((item) => `${item.id} ${item.patient} ${item.complaint}`.toLowerCase().includes(search.toLowerCase()));

  if (view === "detail") return <CaseDetail complaint={complaint} confirmed={confirmed} editing={editing} onComplaint={setComplaint} onEdit={() => setEditing((value) => !value)} onBack={() => setView("list")} onDocument={() => setView("document")} onConfirm={() => setConfirmed(true)} />;
  if (view === "document") return <DocumentReview onBack={() => setView("detail")} />;

  return <main className="mk-doctor-page"><div className="mk-doctor-shell"><header className="mk-doctor-header"><div><p className="mk-eyebrow">Doctor workspace</p><h1>Cases awaiting review</h1><p>Demo workspace · all displayed case information is synthetic.</p></div><StatusBadge tone="neutral">3 demo cases</StatusBadge></header><Card className="mk-case-list"><div className="mk-case-toolbar"><div className="mk-search"><Icon name="search" className="mk-icon" /><Input aria-label="Search demo cases" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search a case" /></div><div className="mk-filter-group"><button type="button" className="mk-filter is-active">All cases</button><button type="button" className="mk-filter">Needs review</button></div></div><div className="mk-case-table" role="table" aria-label="Demo case list"><div className="mk-case-row mk-case-row--head" role="row"><span>Case</span><span>Chief complaint</span><span>Status</span><span>Submitted</span><span /></div>{filtered.map((item) => <button type="button" className="mk-case-row" role="row" key={item.id} onClick={() => setView("detail")}><span><strong>{item.patient}</strong><small>{item.id}</small></span><span>{item.complaint}</span><span><CaseStatus status={item.status} /></span><span>{item.time}</span><Icon name="chevron-right" className="mk-icon" /></button>)}</div>{filtered.length === 0 ? <EmptyState title="No cases found" detail="Try a different patient, session reference, or complaint." /> : null}</Card></div></main>;
}

function CaseStatus({ status }: { status: string }) {
  if (status === "Confirmed") return <StatusBadge tone="success" icon="check">Confirmed</StatusBadge>;
  if (status === "Review needed") return <StatusBadge tone="review">Review needed</StatusBadge>;
  return <StatusBadge tone="neutral">Ready for review</StatusBadge>;
}

function CaseDetail({ complaint, confirmed, editing, onComplaint, onEdit, onBack, onDocument, onConfirm }: { complaint: string; confirmed: boolean; editing: boolean; onComplaint: (value: string) => void; onEdit: () => void; onBack: () => void; onDocument: () => void; onConfirm: () => void }) {
  return <main className="mk-doctor-page"><div className="mk-doctor-shell"><div className="mk-breadcrumb"><button type="button" onClick={onBack}><Icon className="mk-icon" name="arrow-left" />All cases</button><span>/</span><span>MK-DEMO-1042</span></div><header className="mk-doctor-header mk-doctor-header--detail"><div><div className="mk-title-line"><h1>Demo patient</h1><StatusBadge tone={confirmed ? "success" : "review"} icon={confirmed ? "check" : undefined}>{confirmed ? "Confirmed" : "Review needed"}</StatusBadge></div><p>MK-DEMO-1042 · Submitted today at 10:32 · Synthetic demo case</p></div><div className="mk-header-actions"><Button variant="secondary" onClick={onBack}>Back to list</Button><Button onClick={onConfirm} icon="check" disabled={confirmed}>{confirmed ? "Confirmed" : "Confirm case"}</Button></div></header>{confirmed ? <StateNotice title="Case confirmed" detail="The clinician review state is recorded for this demo case." tone="success" /> : null}<div className="mk-doctor-grid"><div className="mk-detail-main"><DoctorSection title="Patient context"><dl className="mk-patient-details"><div><dt>Age</dt><dd>32 years</dd></div><div><dt>Gender</dt><dd>Female</dd></div><div><dt>Language</dt><dd>English</dd></div></dl></DoctorSection><DoctorSection title="Chief complaint" action={<Button variant="quiet" onClick={onEdit} icon="edit">{editing ? "Save field" : "Edit"}</Button>}><div className="mk-field-review">{editing ? <><FieldLabel htmlFor="complaint">Patient statement</FieldLabel><Textarea id="complaint" value={complaint} onChange={(event) => onComplaint(event.target.value)} rows={3} /></> : <p className="mk-clinical-value">{complaint}</p>}<div className="mk-field-meta"><span>Source: patient response</span><span>Structured by: Gemini</span><ConfidenceIndicator state="high" /></div></div></DoctorSection><DoctorSection title="History of present illness"><div className="mk-history-grid"><ReviewField label="Onset" value="Yesterday evening" source="patient response" state="high" /><ReviewField label="Duration" value="Since yesterday" source="patient response" state="high" /><ReviewField label="Severity" value="Moderate" source="patient response" state="high" /><ReviewField label="Associated symptoms" value="Fever, fatigue" source="patient response" state="high" /></div></DoctorSection></div><aside className="mk-detail-side"><DoctorSection title="Documents"><button type="button" className="mk-document-link" onClick={onDocument}><span><Icon name="file" className="mk-icon" /><span><strong>Prescription image</strong><small>1 extraction requires review</small></span></span><Icon name="chevron-right" className="mk-icon" /></button></DoctorSection><DoctorSection title="Review status"><div className="mk-review-checklist"><span><Icon name="check" className="mk-icon" />Patient context reviewed</span><span><Icon name="check" className="mk-icon" />History recorded</span><span><Icon name="help" className="mk-icon" />Document extraction needs review</span></div></DoctorSection></aside></div></div></main>;
}

function DoctorSection({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) { return <Card className="mk-doctor-section"><div className="mk-section-heading"><h2>{title}</h2>{action}</div>{children}</Card>; }

function ReviewField({ label, value, source, state }: { label: string; value: string; source: string; state: "high" | "review" | "corrected" }) { return <div className="mk-review-field"><span>{label}</span><strong>{value}</strong><div><small>Source: {source}</small><ConfidenceIndicator state={state} /></div></div>; }

function DocumentReview({ onBack }: { onBack: () => void }) {
  const [edited, setEdited] = useState(false);
  return <main className="mk-doctor-page"><div className="mk-doctor-shell"><div className="mk-breadcrumb"><button type="button" onClick={onBack}><Icon className="mk-icon" name="arrow-left" />Case MK-DEMO-1042</button><span>/</span><span>Document review</span></div><header className="mk-doctor-header mk-doctor-header--detail"><div><p className="mk-eyebrow">Document review</p><h1>Prescription extraction</h1><p>Review the original document alongside the extracted information.</p></div><Button variant="secondary" onClick={onBack}>Return to case</Button></header><div className="mk-document-split"><Card className="mk-original-document"><div className="mk-document-canvas"><Icon className="mk-icon" name="file" /><p>Original prescription</p><span>Demo document preview</span></div></Card><Card className="mk-extraction-panel"><div className="mk-section-heading"><h2>Extracted information</h2><ConfidenceIndicator state={edited ? "corrected" : "review"} /></div><div className="mk-ocr-row"><div><span>Medicine</span><strong>{edited ? "Paracetamol" : "Paracetemol"}</strong><small>Original extraction: Paracetemol</small></div><Button variant="secondary" onClick={() => setEdited((value) => !value)} icon="edit">{edited ? "Undo" : "Correct"}</Button></div><div className="mk-ocr-row"><div><span>Strength</span><strong>500 mg</strong><small>Source: document extraction</small></div><ConfidenceIndicator state="high" /></div><div className="mk-ocr-row"><div><span>Frequency</span><strong>Twice daily</strong><small>Source: document extraction</small></div><ConfidenceIndicator state="high" /></div><StateNotice title="Review required" detail="Extraction confidence describes readability of the source document, not medical certainty." /></Card></div></div></main>;
}
