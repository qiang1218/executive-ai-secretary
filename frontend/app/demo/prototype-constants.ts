import type {
  ExecutiveProfile,
  OrganizationOption,
  SidebarProject,
  UiLanguage,
  WorkspaceNavigationId,
} from "./prototype-types";

export const ALL_ORGANIZATIONS_ID = "all";
export const COMPOSER_MAX_LENGTH = 8000;
export const COMPOSER_HINT_THRESHOLD = COMPOSER_MAX_LENGTH * 0.8;

export const organizationCatalog: OrganizationOption[] = [
  { id: ALL_ORGANIZATIONS_ID, labels: { "zh-CN": "全部事业部", "zh-TW": "全部事業部", en: "All business units" }, enabled: true, order: 0, dataStatus: "available" },
  { id: "east", labels: { "zh-CN": "华东事业部", "zh-TW": "華東事業部", en: "East China" }, enabled: true, order: 10, dataStatus: "available" },
  { id: "south", labels: { "zh-CN": "华南事业部", "zh-TW": "華南事業部", en: "South China" }, enabled: true, order: 20, dataStatus: "available" },
  { id: "north", labels: { "zh-CN": "北区事业部", "zh-TW": "北區事業部", en: "North Region" }, enabled: true, order: 30, dataStatus: "available" },
];

export const availableOrganizations = organizationCatalog
  .filter((organization) => organization.enabled && organization.dataStatus === "available")
  .sort((first, second) => first.order - second.order);

export const owners = ["陈岚", "林序", "唐昱", "顾宁"];

export const workspaceNavigation: Array<{ id: WorkspaceNavigationId; label: string; short: string }> = [
  { id: "daily", label: "今日经营简报", short: "今" },
  { id: "weekly", label: "每周高层简报", short: "周" },
  { id: "history", label: "历史会话", short: "历" },
  { id: "memory", label: "长期记忆", short: "记" },
];

export const initialSidebarProjects: SidebarProject[] = [
  {
    id: "collection",
    title: "回款与现金流",
    description: "持续跟进回款差距、逾期应收与现金流风险。",
    conversationIds: [7, 8],
  },
  {
    id: "delivery",
    title: "重点项目交付",
    description: "集中查看重点项目、交付里程碑与复盘事项。",
    conversationIds: [9, 10],
  },
];

export const languageOptions: Array<{ id: UiLanguage; label: string }> = [
  { id: "zh-CN", label: "简体中文" },
  { id: "zh-TW", label: "繁體中文" },
  { id: "en", label: "English" },
];

export const workbenchCopy = {
  "zh-CN": {
    brand: "董事长 AI 秘书", brandSubtitle: "经营决策工作台", newConversation: "新建会话",
    navigation: { daily: "今日经营简报", weekly: "每周高层简报", history: "历史会话", memory: "长期记忆" },
    pinned: "置顶", projects: "项目", recent: "最近", all: "全部", dataAvailable: "企业数据可用", updatedAt: "更新至 02:06",
    role: "董事长", settings: "设置", language: "语言", logout: "退出登录", demo: "演示",
    morningTitle: "今日有 2 项需要确认", morningMeta: "晨间简报 · 数据截至 7月25日 02:06", morningAction: "查看晨间摘要",
    date: "2026年7月26日，星期日", greeting: "早上好", greetingQuestion: "今天需要我先看什么？",
    composerPlaceholder: "向 AI 秘书提问经营数据，或上传当前会话文件", continuePlaceholder: "继续追问，当前范围会自动继承",
    file: "文件", startQuestion: "从一个问题开始", disclaimer: "AI 可能出错。关键经营数字请结合来源与数据时间核对。",
    chooseOrganization: "选择事业部", searchOrganization: "搜索事业部", configuredByAdmin: "可选范围由企业管理员配置", apply: "应用",
    selectedOrganizations: (count: number) => `已选 ${count} 个事业部`, noOrganizations: "没有匹配的事业部",
    remainingCharacters: (count: number) => `还可输入 ${count.toLocaleString("zh-CN")} 字`,
  },
  "zh-TW": {
    brand: "董事長 AI 秘書", brandSubtitle: "經營決策工作台", newConversation: "新建會話",
    navigation: { daily: "今日經營簡報", weekly: "每週高層簡報", history: "歷史會話", memory: "長期記憶" },
    pinned: "置頂", projects: "項目", recent: "最近", all: "全部", dataAvailable: "企業資料可用", updatedAt: "更新至 02:06",
    role: "董事長", settings: "設定", language: "語言", logout: "登出", demo: "演示",
    morningTitle: "今日有 2 項需要確認", morningMeta: "晨間簡報 · 資料截至 7月25日 02:06", morningAction: "查看晨間摘要",
    date: "2026年7月26日，星期日", greeting: "早上好", greetingQuestion: "今天需要我先看什麼？",
    composerPlaceholder: "向 AI 秘書提問經營資料，或上傳目前會話檔案", continuePlaceholder: "繼續追問，目前範圍會自動繼承",
    file: "檔案", startQuestion: "從一個問題開始", disclaimer: "AI 可能出錯。關鍵經營數字請結合來源與資料時間核對。",
    chooseOrganization: "選擇事業部", searchOrganization: "搜尋事業部", configuredByAdmin: "可選範圍由企業管理員配置", apply: "套用",
    selectedOrganizations: (count: number) => `已選 ${count} 個事業部`, noOrganizations: "沒有符合的事業部",
    remainingCharacters: (count: number) => `還可輸入 ${count.toLocaleString("zh-TW")} 字`,
  },
  en: {
    brand: "Chairman's AI Secretary", brandSubtitle: "Executive decision workspace", newConversation: "New conversation",
    navigation: { daily: "Daily brief", weekly: "Weekly executive brief", history: "Conversation history", memory: "Long-term memory" },
    pinned: "Pinned", projects: "Projects", recent: "Recent", all: "All", dataAvailable: "Enterprise data available", updatedAt: "Updated 02:06",
    role: "Chairman", settings: "Settings", language: "Language", logout: "Sign out", demo: "Demo",
    morningTitle: "2 items need confirmation", morningMeta: "Morning brief · Data through Jul 25, 02:06", morningAction: "View morning brief",
    date: "Sunday, July 26, 2026", greeting: "Good morning", greetingQuestion: "What should I look into first?",
    composerPlaceholder: "Ask about the business or upload a file for this conversation", continuePlaceholder: "Ask a follow-up; the current scope will carry over",
    file: "File", startQuestion: "Start with a question", disclaimer: "AI can make mistakes. Verify critical figures against sources and data timestamps.",
    chooseOrganization: "Choose business units", searchOrganization: "Search business units", configuredByAdmin: "Available scope is configured by your administrator", apply: "Apply",
    selectedOrganizations: (count: number) => `${count} business units selected`, noOrganizations: "No matching business units",
    remainingCharacters: (count: number) => `${count.toLocaleString("en")} characters remaining`,
  },
} as const;

export const initialExecutiveProfile: ExecutiveProfile = {
  displayName: "Ryan.Zhang",
  salutation: "董事长",
  amountUnit: "万元",
  emailMasked: "z153***@gmail.com",
  lastLoginAt: "2026年7月26日 13:06",
};
