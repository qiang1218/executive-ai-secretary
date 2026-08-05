import type { ReactNode } from "react";

export type UiIconName =
  | "settings"
  | "language"
  | "logout"
  | "chevron"
  | "search"
  | "profile"
  | "appearance"
  | "memory"
  | "system"
  | "light"
  | "dark"
  | "edit"
  | "shield"
  | "pin"
  | "archive"
  | "remove"
  | "folder"
  | "organization";

const ICON_PATHS: Record<UiIconName, ReactNode> = {
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.9 1.9-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1 1.55V20h-2.7v-.09a1.7 1.7 0 0 0-1.07-1.55 1.7 1.7 0 0 0-1.88.34l-.06.06-1.9-1.9.06-.06A1.7 1.7 0 0 0 7.75 15a1.7 1.7 0 0 0-1.55-1H6v-2.7h.09a1.7 1.7 0 0 0 1.55-1.07 1.7 1.7 0 0 0-.34-1.88l-.06-.06 1.9-1.9.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 12.1 5.2V5h2.7v.09a1.7 1.7 0 0 0 1.07 1.55 1.7 1.7 0 0 0 1.88-.34l.06-.06 1.9 1.9-.06.06a1.7 1.7 0 0 0-.34 1.88A1.7 1.7 0 0 0 20.8 11v2.7h-.09A1.7 1.7 0 0 0 19.4 15Z" />
    </>
  ),
  language: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.8 12h16.4M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5S14.3 18.1 12 20.5M12 3.5C9.7 5.9 8.6 8.7 8.6 12s1.1 6.1 3.4 8.5" />
    </>
  ),
  logout: (
    <>
      <path d="M10 5H6.5A2.5 2.5 0 0 0 4 7.5v9A2.5 2.5 0 0 0 6.5 19H10" />
      <path d="m14 8 4 4-4 4M18 12H9" />
    </>
  ),
  chevron: <path d="m9 6 6 6-6 6" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="m15 15 4.5 4.5" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 19c.8-3.2 3-5 6.5-5s5.7 1.8 6.5 5" />
    </>
  ),
  appearance: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 3.5v17M3.5 12h17M6 6l12 12M18 6 6 18" />
    </>
  ),
  memory: (
    <>
      <path d="M7 5.5h8.5A2.5 2.5 0 0 1 18 8v10l-6-3-6 3V6.5A1 1 0 0 1 7 5.5Z" />
      <path d="M9 9h6" />
    </>
  ),
  system: (
    <>
      <rect x="3.5" y="4.5" width="17" height="11" rx="2" />
      <path d="M9 19.5h6M12 15.5v4" />
    </>
  ),
  light: (
    <>
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4" />
    </>
  ),
  dark: <path d="M19.5 15.5A8 8 0 0 1 8.5 4.5a8.2 8.2 0 1 0 11 11Z" />,
  edit: (
    <>
      <path d="m5 16-.7 3.7L8 19l9.8-9.8-3-3L5 16Z" />
      <path d="m13.8 7.2 3 3" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3.5 19 6v5.4c0 4.2-2.3 7.1-7 9.1-4.7-2-7-4.9-7-9.1V6l7-2.5Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  pin: (
    <>
      <path d="m14 4 6 6-3 1-3.5 3.5 1 3-1.5 1.5-4-4-4.5 4.5" />
      <path d="m7 8 3 1L13.5 5l.5-1Z" />
    </>
  ),
  archive: (
    <>
      <rect x="4" y="5" width="16" height="4" rx="1" />
      <path d="M6 9v9.5h12V9M10 13h4" />
    </>
  ),
  remove: (
    <>
      <path d="M5 5l14 14M19 5 5 19" />
    </>
  ),
  folder: (
    <>
      <path d="M3.5 7.5h6l2-2h8a1.5 1.5 0 0 1 1.5 1.5v10.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a1.5 1.5 0 0 1 .5-1.5Z" />
      <path d="M3.5 9h17.5" />
    </>
  ),
  organization: (
    <>
      <path d="M5 20V9l4-3v14M9 20h10V4l-6 3v13M3 20h18" />
      <path d="M12 10h2M12 14h2M16 8h1M16 12h1" />
    </>
  ),
};

export function UiIcon({ name }: { name: UiIconName }) {
  return (
    <svg
      className="ui-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICON_PATHS[name]}
    </svg>
  );
}
