import type { ExecutiveView, RouteKind, Tone } from "./prototype-data";

export type AuthRole = "executive" | "admin" | null;
export type LoginMode = Exclude<AuthRole, null>;
export type AuthStep = "login" | "change-password";
export type ThemePreference = "system" | "light" | "dark";
export type UiLanguage = "zh-CN" | "zh-TW" | "en";
export type PersonalCenterView = "profile" | "appearance" | "memory";
export type WorkspacePanelView = Exclude<ExecutiveView, "home" | "chat">;
export type WorkspaceNavigationId = "daily" | "weekly" | "history" | "memory";

export type ChatStage =
  | "empty"
  | "clarifying"
  | "understanding"
  | "working"
  | "composing"
  | "ready"
  | "stopped"
  | "offline";

export type FileStatus = "上传中" | "等待解析" | "解析中" | "可使用" | "部分解析" | "解析失败";

export type ConfirmState = {
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "danger" | "normal";
  action: () => void;
};

export type DemoFile = {
  id: number;
  name: string;
  kind: string;
  size: string;
  status: FileStatus;
  uploadedAt: string;
  range: string;
  error?: string;
};

export type ScopeState = {
  time: string;
  organizationIds: string[];
  owner: string;
  object: string;
};

export type OrganizationOption = {
  id: string;
  labels: Record<UiLanguage, string>;
  enabled: boolean;
  order: number;
  dataStatus: "available" | "syncing" | "unavailable";
};

export type ExecutiveProfile = {
  displayName: string;
  salutation: string;
  amountUnit: string;
  emailMasked: string;
  lastLoginAt: string;
};

export type RouteRecord = {
  id: number;
  time: string;
  route: RouteKind;
  summary: string;
  status: "待补充范围" | "已路由" | "待网络确认";
};

export type SidebarMenuState =
  | { kind: "conversation"; conversationId: number; top: number }
  | { kind: "project"; projectId: string; top: number };

export type SidebarProject = {
  id: string;
  title: string;
  description: string;
  conversationIds: number[];
};

export type ProjectDialogState =
  | { mode: "create" }
  | { mode: "edit"; projectId: string };

export type UiIconName =
  | "settings"
  | "language"
  | "logout"
  | "chevron"
  | "search"
  | "check"
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
  | "folder";

// Re-export for convenience so consumers can import from a single module.
export type { ExecutiveView, RouteKind, Tone };
