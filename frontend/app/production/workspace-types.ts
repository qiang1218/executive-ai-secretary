import type {
  DailyBrief,
  ExecutivePersonalProfile,
  OrganizationScope,
} from "./types";

export type ThemePreference = "system" | "light" | "dark";
export type UiLanguage = "zh-CN" | "zh-TW" | "en";
export type WorkspacePanel = "daily" | "weekly" | "history" | "memory" | "scope";
export type PreferencesView = "profile" | "appearance" | "memory";
export type ProjectDialogState = { mode: "create" } | { mode: "edit"; projectId: string };
export type ConversationProjectDialogState = { conversationId: string };
export type SidebarMenuState =
  | { kind: "conversation"; conversationId: string; top: number }
  | { kind: "project"; projectId: string; top: number };
export type ConfirmState = {
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "normal" | "danger";
  action: () => void | Promise<void>;
};
export type ProfilePreferences = {
  salutation: string;
  amountUnit: ExecutivePersonalProfile["amount_unit"];
  responseStyle: ExecutivePersonalProfile["response_style"];
};
export type DailyBriefLoadState = {
  scopeKey: string;
  status: "ready" | "loading" | "error";
  data: DailyBrief | null;
};
export type MemoryUpdateValues = {
  title?: string;
  content?: string;
  status?: "active" | "disabled" | "deleted";
};
export type MemoryCreateHandler = (
  title: string,
  content: string,
  kind: string,
  organizationUnitId: string | null,
) => Promise<boolean>;
export type MemoryUpdateHandler = (
  memory: import("./types").Memory,
  values: MemoryUpdateValues,
) => Promise<boolean>;

export const ALL_SCOPE_ID = "all";
export const ALL_ORGANIZATIONS_SCOPE: OrganizationScope = {
  mode: "all_authorized",
  organization_unit_ids: [],
};
export const COMPOSER_MAX_LENGTH = 8000;
export const COMPOSER_HINT_THRESHOLD = COMPOSER_MAX_LENGTH * 0.8;

export const languageOptions: Array<{ id: UiLanguage; label: string }> = [
  { id: "zh-CN", label: "简体中文" },
  { id: "zh-TW", label: "繁體中文" },
  { id: "en", label: "English" },
];

export const copy = {
  "zh-CN": {
    brand: "董事长 AI 秘书",
    newConversation: "新建会话",
    daily: "今日经营简报",
    weekly: "每周高层简报",
    history: "历史会话",
    memory: "长期记忆",
    pinned: "置顶",
    projects: "项目",
    recent: "最近",
    all: "全部",
    settings: "设置",
    language: "语言",
    logout: "退出登录",
    profile: "个人资料",
    appearance: "外观",
    scope: "全部事业部",
    placeholder: "向 AI 秘书提问经营数据，或讨论需要分析的问题",
    disclaimer: "AI 可能出错。关键经营数字请结合来源与数据时间核对。",
    noProject: "尚未创建项目",
    noConversation: "尚无历史会话",
    dataReady: "企业数据可用",
    dataMissing: "尚未配置数据范围",
  },
  "zh-TW": {
    brand: "董事長 AI 秘書",
    newConversation: "新建會話",
    daily: "今日經營簡報",
    weekly: "每週高層簡報",
    history: "歷史會話",
    memory: "長期記憶",
    pinned: "置頂",
    projects: "項目",
    recent: "最近",
    all: "全部",
    settings: "設定",
    language: "語言",
    logout: "登出",
    profile: "個人資料",
    appearance: "外觀",
    scope: "全部事業部",
    placeholder: "向 AI 秘書提問經營資料，或討論需要分析的問題",
    disclaimer: "AI 可能出錯。關鍵經營數字請結合來源與資料時間核對。",
    noProject: "尚未建立項目",
    noConversation: "尚無歷史會話",
    dataReady: "企業資料可用",
    dataMissing: "尚未設定資料範圍",
  },
  en: {
    brand: "Chairman's AI Secretary",
    newConversation: "New conversation",
    daily: "Daily brief",
    weekly: "Weekly executive brief",
    history: "Conversation history",
    memory: "Long-term memory",
    pinned: "Pinned",
    projects: "Projects",
    recent: "Recent",
    all: "All",
    settings: "Settings",
    language: "Language",
    logout: "Sign out",
    profile: "Profile",
    appearance: "Appearance",
    scope: "All business units",
    placeholder: "Ask about the business or discuss a question that needs analysis",
    disclaimer: "AI can make mistakes. Verify critical figures against sources and data timestamps.",
    noProject: "No projects yet",
    noConversation: "No conversations yet",
    dataReady: "Enterprise data available",
    dataMissing: "No data scope configured",
  },
} as const;
