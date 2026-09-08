import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { Icon, type IconName } from "./icons";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet";
  loading?: boolean;
  icon?: IconName;
};

export function Button({ children, className = "", variant = "primary", loading = false, icon, disabled, ...props }: ButtonProps) {
  return (
    <button className={`mk-button mk-button--${variant} ${className}`} disabled={disabled || loading} {...props}>
      {loading ? <span className="mk-spinner" aria-hidden="true" /> : icon ? <Icon className="mk-icon" name={icon} /> : null}
      <span>{children}</span>
    </button>
  );
}

export function Card({ children, className = "", as: Tag = "section" }: { children: ReactNode; className?: string; as?: "section" | "article" | "div" }) {
  return <Tag className={`mk-card ${className}`}>{children}</Tag>;
}

export function FieldLabel({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return <label className="mk-field-label" htmlFor={htmlFor}>{children}</label>;
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`mk-input ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`mk-textarea ${className}`} {...props} />;
}

export function StatusBadge({ children, tone = "review", icon }: { children: ReactNode; tone?: "success" | "review" | "danger" | "neutral"; icon?: IconName }) {
  return <span className={`mk-status mk-status--${tone}`}>{icon ? <Icon className="mk-icon mk-icon--inline" name={icon} /> : null}{children}</span>;
}

export function ConfidenceIndicator({ state }: { state: "high" | "review" | "corrected" }) {
  const copy = { high: "High confidence", review: "Review", corrected: "Manually corrected" }[state];
  const tone = state === "high" ? "success" : "review";
  return <StatusBadge tone={tone} icon={state === "corrected" ? "edit" : state === "high" ? "check" : undefined}>{copy}</StatusBadge>;
}

export function ProgressIndicator({ current, total, label }: { current: number; total: number; label: string }) {
  const percentage = Math.round((current / total) * 100);
  return (
    <div className="mk-progress" aria-label={`${label}: step ${current} of ${total}`}>
      <div className="mk-progress__meta"><span>{label}</span><span>Step {current} of {total}</span></div>
      <div className="mk-progress__track" aria-hidden="true"><span className="mk-progress__value" style={{ width: `${percentage}%` }} /></div>
    </div>
  );
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <div className="mk-empty-state"><h2>{title}</h2><p>{detail}</p>{action}</div>;
}

export function StateNotice({ title, detail, tone = "neutral", action }: { title: string; detail: string; tone?: "neutral" | "danger" | "success"; action?: ReactNode }) {
  return <div className={`mk-state-notice mk-state-notice--${tone}`} role={tone === "danger" ? "alert" : "status"}><div><strong>{title}</strong><p>{detail}</p></div>{action}</div>;
}
