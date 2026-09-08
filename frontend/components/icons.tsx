import type { SVGProps } from "react";

export type IconName =
  | "arrow-right"
  | "arrow-left"
  | "check"
  | "chevron-right"
  | "edit"
  | "file"
  | "help"
  | "language"
  | "lock"
  | "mic"
  | "pause"
  | "play"
  | "search"
  | "shield"
  | "upload"
  | "x";

const paths: Record<IconName, React.ReactNode> = {
  "arrow-right": <path d="M5 12h14m-6-6 6 6-6 6" />,
  "arrow-left": <path d="M19 12H5m6 6-6-6 6-6" />,
  check: <path d="m5 12 4 4L19 6" />,
  "chevron-right": <path d="m9 18 6-6-6-6" />,
  edit: <><path d="M12 20h8" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h5" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.6 2.6 0 1 1 4.2 2c-1.1.8-1.7 1.2-1.7 2.5" /><path d="M12 17h.01" /></>,
  language: <><path d="M5 4h9M9.5 4c0 7-2.5 11-5.5 13M6 9h7M14 20l4-9 4 9m-7-3h6" /></>,
  lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" /></>,
  pause: <><path d="M8 5v14M16 5v14" /></>,
  play: <path d="m9 5 10 7-10 7Z" />,
  search: <><circle cx="11" cy="11" r="6" /><path d="m20 20-4-4" /></>,
  shield: <path d="M12 3 5 6v5c0 5 3 8.5 7 10 4-1.5 7-5 7-10V6Z" />,
  upload: <><path d="M12 16V4m0 0L8 8m4-4 4 4" /><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" /></>,
  x: <path d="m6 6 12 12M18 6 6 18" />,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>
      {paths[name]}
    </svg>
  );
}
