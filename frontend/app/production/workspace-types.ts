import type {
  DailyBrief,
  ExecutivePersonalProfile,
  OrganizationScope,
} from "./types";

export type ThemePreference = "system" | "light" | "dark";
export type UiLanguage = "zh-CN" | "zh-TW" | "en";
export type WorkspacePanel = "daily" | "weekly" | "history" | "memory" | "scope" | "email";
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
    briefLoading: "正在核对今日事项",
    briefError: "晨间简报暂不可用",
    briefDataThrough: "晨间简报 · 数据截至",
    briefDataPending: "晨间简报 · 数据状态待确认",
    briefLoadingScope: "晨间简报 · 正在核对当前范围",
    briefErrorRetry: "晨间简报 · 请检查数据状态后重试",
    briefViewReport: "查看晨间摘要",
    suggestionsAria: "建议问题",
    suggestions: ["整理本月经营变化", "查看需要我确认的事项", "起草三分钟经营会汇报"],
    briefMetaLabel: "晨间经营摘要",
    briefExplanation: "仅呈现需要高层确认的实质事项，不以普通变化补足数量。",
    dataThrough: "数据截至",
    itemsAttention: "需要确认的事项",
    noItemsClear: "当前范围内未识别到需要确认的重大事项。",
    noItemsUncertain: "当前数据不完整，暂不能确认没有需要处理的事项。",
    dataScopeReadiness: "数据范围与就绪度",
    scopeLabel: "范围",
    allAuthorizedUnits: "全部授权事业部",
    unitCountSuffix: "个事业部",
    recordsSuffix: " 条",
    prefsTitle: "个人设置",
    prefsBack: "返回工作台",
    prefsClose: "关闭",
    businessUnitScope: "选择事业部",
    searchBusinessUnits: "搜索事业部",
    apply: "应用",
    charsRemainingPrefix: "还可输入",
    charsRemainingSuffix: "字",
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
    briefLoading: "正在核對今日事項",
    briefError: "晨間簡報暫不可用",
    briefDataThrough: "晨間簡報 · 數據截至",
    briefDataPending: "晨間簡報 · 數據狀態待確認",
    briefLoadingScope: "晨間簡報 · 正在核對目前範圍",
    briefErrorRetry: "晨間簡報 · 請檢查數據狀態後重試",
    briefViewReport: "查看晨間摘要",
    suggestionsAria: "建議問題",
    suggestions: ["整理本月經營變化", "查看需要我確認的事項", "起草三分鐘經營會匯報"],
    briefMetaLabel: "晨間經營摘要",
    briefExplanation: "僅呈現需要高層確認的實質事項，不以普通變化補足數量。",
    dataThrough: "數據截至",
    itemsAttention: "需要確認的事項",
    noItemsClear: "目前範圍內未識別到需要確認的重大事項。",
    noItemsUncertain: "目前數據不完整，暫不能確認沒有需要處理的事項。",
    dataScopeReadiness: "數據範圍與就緒度",
    scopeLabel: "範圍",
    allAuthorizedUnits: "全部授權事業部",
    unitCountSuffix: "個事業部",
    recordsSuffix: " 條",
    prefsTitle: "個人設定",
    prefsBack: "返回工作台",
    prefsClose: "關閉",
    businessUnitScope: "選擇事業部",
    searchBusinessUnits: "搜尋事業部",
    apply: "套用",
    charsRemainingPrefix: "還可輸入",
    charsRemainingSuffix: "字",
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
    briefLoading: "Reviewing today's priorities",
    briefError: "Morning brief is temporarily unavailable",
    briefDataThrough: "Morning brief · Data through",
    briefDataPending: "Morning brief · Data status pending",
    briefLoadingScope: "Morning brief · Checking the current scope",
    briefErrorRetry: "Morning brief · Check data status and try again",
    briefViewReport: "View morning brief",
    suggestionsAria: "Suggested questions",
    suggestions: ["Summarize this month's operating changes", "Show items that need my confirmation", "Draft a three-minute executive update"],
    briefMetaLabel: "Morning executive brief",
    briefExplanation: "Only material items that require an executive confirmation are shown here.",
    dataThrough: "Data through",
    itemsAttention: "Items needing attention",
    noItemsClear: "No material confirmation item was identified for the current scope.",
    noItemsUncertain: "The current data is incomplete, so the system cannot confirm that there are no action items.",
    dataScopeReadiness: "Data scope and readiness",
    scopeLabel: "Scope",
    allAuthorizedUnits: "All authorized business units",
    unitCountSuffix: " business units",
    recordsSuffix: " records",
    prefsTitle: "Personal settings",
    prefsBack: "Back to workspace",
    prefsClose: "Close",
    businessUnitScope: "Business unit scope",
    searchBusinessUnits: "Search business units",
    apply: "Apply",
    charsRemainingPrefix: "",
    charsRemainingSuffix: "characters remaining",
  },
} as const;
