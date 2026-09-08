"use client";

import { useRef, useState } from "react";
import { Button, Card, FieldLabel, Input, ProgressIndicator, StateNotice, Textarea } from "./ui";
import { Icon } from "./icons";

type Screen = "welcome" | "language" | "interview" | "choice" | "voice" | "upload" | "review" | "complete";

const languages = ["English", "ગુજરાતી", "हिन्दी"];

export function PatientFlow() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [language, setLanguage] = useState("English");
  const [answer, setAnswer] = useState("");
  const [choice, setChoice] = useState("");
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [fileName, setFileName] = useState("");
  const [corrected, setCorrected] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const continueInterview = () => {
    if (!answer.trim()) {
      setError("Please tell us what problem you are experiencing before continuing.");
      return;
    }
    setError("");
    setScreen("choice");
  };

  const mainScreen = (() => {
    switch (screen) {
      case "welcome":
        return <Welcome onStart={() => setScreen("language")} />;
      case "language":
        return <Language selected={language} onSelect={setLanguage} onBack={() => setScreen("welcome")} onContinue={() => setScreen("interview")} />;
      case "interview":
        return <Interview answer={answer} error={error} onAnswer={(value) => { setAnswer(value); setError(""); }} onContinue={continueInterview} onVoice={() => setScreen("voice")} />;
      case "choice":
        return <ChoiceQuestion selected={choice} onSelect={setChoice} onBack={() => setScreen("interview")} onContinue={() => choice ? setScreen("upload") : setError("Select an option to continue.")} error={error} />;
      case "voice":
        return <VoiceInput recording={recording} onToggle={() => setRecording((value) => !value)} onBack={() => setScreen("interview")} onContinue={() => setScreen("choice")} />;
      case "upload":
        return <Upload fileName={fileName} inputRef={fileInput} onSelect={(name) => setFileName(name)} onBack={() => setScreen("choice")} onContinue={() => fileName ? setScreen("review") : setError("Choose a document to continue, or select Skip for now.")} onSkip={() => setScreen("complete")} error={error} />;
      case "review":
        return <OcrReview corrected={corrected} onCorrect={() => setCorrected((value) => !value)} onBack={() => setScreen("upload")} onContinue={() => setScreen("complete")} />;
      case "complete":
        return <Completion onRestart={() => { setAnswer(""); setChoice(""); setFileName(""); setCorrected(false); setScreen("welcome"); }} />;
    }
  })();

  const progress = screen === "welcome" || screen === "language" ? null : <ProgressIndicator current={screen === "interview" || screen === "voice" ? 1 : screen === "choice" ? 2 : screen === "upload" || screen === "review" ? 3 : 4} total={4} label="Your case-taking" />;

  return <main className="mk-patient-page"><div className="mk-patient-shell">{progress}{mainScreen}</div></main>;
}

function Welcome({ onStart }: { onStart: () => void }) {
  return <Card className="mk-patient-welcome"><div className="mk-brand-mark"><Icon name="shield" className="mk-icon" /></div><p className="mk-eyebrow">MediKiosk</p><h1>Your consultation starts with a few simple questions.</h1><p className="mk-patient-body">Share what you are experiencing. Your clinician will review and confirm the information before your consultation.</p><div className="mk-patient-actions"><Button onClick={onStart} icon="arrow-right">Start</Button><button className="mk-help-link" type="button"><Icon className="mk-icon" name="help" />Need help?</button></div><p className="mk-privacy"><Icon className="mk-icon mk-icon--inline" name="lock" />Your information is collected for this consultation only.</p></Card>;
}

function Language({ selected, onSelect, onBack, onContinue }: { selected: string; onSelect: (language: string) => void; onBack: () => void; onContinue: () => void }) {
  return <Card className="mk-patient-card"><p className="mk-eyebrow">MediKiosk</p><h1 className="mk-patient-section">Choose your language</h1><p className="mk-patient-body">You can continue in the language that feels most comfortable.</p><div className="mk-choice-list" role="radiogroup" aria-label="Language">
    {languages.map((language) => <button className={`mk-choice ${selected === language ? "is-selected" : ""}`} type="button" key={language} role="radio" aria-checked={selected === language} onClick={() => onSelect(language)}><span>{language}</span>{selected === language ? <Icon className="mk-icon" name="check" /> : <span className="mk-choice__circle" aria-hidden="true" />}</button>)}
  </div><div className="mk-patient-actions"><Button variant="secondary" onClick={onBack} icon="arrow-left">Back</Button><Button onClick={onContinue} icon="arrow-right">Continue</Button></div></Card>;
}

function Interview({ answer, error, onAnswer, onContinue, onVoice }: { answer: string; error: string; onAnswer: (value: string) => void; onContinue: () => void; onVoice: () => void }) {
  return <Card className="mk-patient-card"><p className="mk-eyebrow">Tell us about your visit</p><h1 className="mk-patient-question">What is the main problem you are experiencing?</h1><p className="mk-patient-helper">For example: “I have had a headache and fever since yesterday.”</p><FieldLabel htmlFor="patient-answer">Your answer</FieldLabel><Textarea id="patient-answer" value={answer} onChange={(event) => onAnswer(event.target.value)} aria-describedby={error ? "patient-answer-error" : undefined} aria-invalid={Boolean(error)} placeholder="Type your answer here" rows={4} />{error ? <StateNotice title="Please check your answer" detail={error} tone="danger" /> : null}<div className="mk-patient-actions"><Button variant="secondary" onClick={onVoice} icon="mic">Use voice instead</Button><Button onClick={onContinue} icon="arrow-right">Continue</Button></div></Card>;
}

function ChoiceQuestion({ selected, onSelect, onBack, onContinue, error }: { selected: string; onSelect: (value: string) => void; onBack: () => void; onContinue: () => void; error: string }) {
  const choices = ["Mild — I can continue my usual activities", "Moderate — it is affecting my usual activities", "Severe — I need help soon"];
  return <Card className="mk-patient-card"><p className="mk-eyebrow">A little more detail</p><h1 className="mk-patient-question">How much is this problem affecting you?</h1><p className="mk-patient-helper">Choose the option that describes your experience best.</p><div className="mk-choice-list" role="radiogroup" aria-label="Severity">
    {choices.map((item) => <button className={`mk-choice ${selected === item ? "is-selected" : ""}`} type="button" key={item} role="radio" aria-checked={selected === item} onClick={() => onSelect(item)}><span>{item}</span>{selected === item ? <Icon className="mk-icon" name="check" /> : <span className="mk-choice__circle" aria-hidden="true" />}</button>)}
  </div>{error ? <StateNotice title="Choose an option" detail={error} tone="danger" /> : null}<div className="mk-patient-actions"><Button variant="secondary" onClick={onBack} icon="arrow-left">Back</Button><Button onClick={onContinue} icon="arrow-right">Continue</Button></div></Card>;
}

function VoiceInput({ recording, onToggle, onBack, onContinue }: { recording: boolean; onToggle: () => void; onBack: () => void; onContinue: () => void }) {
  return <Card className="mk-patient-card"><p className="mk-eyebrow">Voice input</p><h1 className="mk-patient-question">You can speak your answer.</h1><p className="mk-patient-helper">Voice input is optional. You can always type your answer instead.</p><div className={`mk-recording ${recording ? "is-recording" : ""}`}><Icon className="mk-icon mk-recording__icon" name="mic" /><strong>{recording ? "Listening…" : "Ready when you are"}</strong><span>{recording ? "Speak clearly, then select Stop." : "Your recorded answer will appear here for you to review."}</span></div><div className="mk-patient-actions"><Button variant="secondary" onClick={onBack} icon="arrow-left">Type answer</Button><Button onClick={onToggle} icon={recording ? "pause" : "mic"}>{recording ? "Stop" : "Start speaking"}</Button>{recording ? <Button variant="secondary" onClick={onContinue} icon="arrow-right">Continue</Button> : null}</div></Card>;
}

function Upload({ fileName, inputRef, onSelect, onBack, onContinue, onSkip, error }: { fileName: string; inputRef: React.RefObject<HTMLInputElement | null>; onSelect: (name: string) => void; onBack: () => void; onContinue: () => void; onSkip: () => void; error: string }) {
  return <Card className="mk-patient-card"><p className="mk-eyebrow">Optional document</p><h1 className="mk-patient-section">Do you have a prescription or report to add?</h1><p className="mk-patient-body">You can upload a clear photo or PDF. Your clinician will review any extracted information.</p><input className="mk-visually-hidden" ref={inputRef} type="file" accept="image/jpeg,image/png,application/pdf" onChange={(event) => onSelect(event.target.files?.[0]?.name ?? "")} /><button type="button" className={`mk-upload ${fileName ? "is-success" : ""}`} onClick={() => inputRef.current?.click()}>{fileName ? <><Icon className="mk-icon" name="check" /><strong>{fileName}</strong><span>Selected successfully. Select again to replace it.</span></> : <><Icon className="mk-icon" name="upload" /><strong>Choose a document</strong><span>JPG, PNG, or PDF · up to 10 MB</span></>}</button>{error ? <StateNotice title="Choose a document or skip" detail={error} tone="danger" /> : null}<div className="mk-patient-actions"><Button variant="secondary" onClick={onBack} icon="arrow-left">Back</Button><Button variant="secondary" onClick={onSkip}>Skip for now</Button><Button onClick={onContinue} icon="arrow-right">Review</Button></div></Card>;
}

function OcrReview({ corrected, onCorrect, onBack, onContinue }: { corrected: boolean; onCorrect: () => void; onBack: () => void; onContinue: () => void }) {
  return <Card className="mk-patient-card"><p className="mk-eyebrow">Check extracted information</p><h1 className="mk-patient-section">Please review what we found.</h1><p className="mk-patient-helper">This is a draft from your document, not a medical decision. You can correct it before continuing.</p><div className="mk-document-review"><div className="mk-document-preview"><Icon className="mk-icon" name="file" /><span>Original document</span></div><div className="mk-extraction"><div className="mk-extraction__meta"><span>Extracted medicine</span><span className="mk-status mk-status--review">Review</span></div><strong>{corrected ? "Paracetamol 500 mg" : "Paracetemol 500 mg"}</strong><p>Source: document extraction</p><Button variant="secondary" onClick={onCorrect} icon="edit">{corrected ? "Undo correction" : "Correct value"}</Button>{corrected ? <p className="mk-corrected-note">Original extraction kept: “Paracetemol 500 mg”</p> : null}</div></div><div className="mk-patient-actions"><Button variant="secondary" onClick={onBack} icon="arrow-left">Back</Button><Button onClick={onContinue} icon="arrow-right">Continue</Button></div></Card>;
}

function Completion({ onRestart }: { onRestart: () => void }) {
  return <Card className="mk-patient-welcome"><div className="mk-success-mark"><Icon className="mk-icon" name="check" /></div><p className="mk-eyebrow">Submitted</p><h1>Your information is ready for review.</h1><p className="mk-patient-body">A clinician will review your responses and documents with you. No diagnosis has been made by MediKiosk.</p><div className="mk-session-token"><span>Session reference</span><strong>MK-DEMO-1042</strong></div><div className="mk-patient-actions"><Button onClick={onRestart}>Start a new session</Button></div></Card>;
}
