"use client";

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  MouseEvent as ReactMouseEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AnswerConfig,
  ConversationItem,
  ExecutiveView,
  MemoryItem,
  RouteKind,
  answerConfigs,
  initialConversations,
  initialMemories,
} from "./prototype-data";
import type {
  AuthRole,
  AuthStep,
  ChatStage,
  ConfirmState,
  DemoFile,
  ExecutiveProfile,
  LoginMode,
  PersonalCenterView,
  ProjectDialogState,
  RouteRecord,
  ScopeState,
  SidebarMenuState,
  SidebarProject,
  ThemePreference,
  UiLanguage,
  WorkspacePanelView,
} from "./prototype-types";
import {
  ALL_ORGANIZATIONS_ID,
  availableOrganizations,
  initialExecutiveProfile,
  initialSidebarProjects,
  languageOptions,
  workbenchCopy,
  workspaceNavigation,
} from "./prototype-constants";
import {
  copyToClipboard,
  demoReadyFile,
  fileRange,
  formatFileSize,
  formatOrganizationSelection,
  makeConversationTitle,
  makeTaskTitle,
  safeRouteSummary,
} from "./prototype-utils";
import {
  AccountView,
  AdminWorkspace,
  CapabilitiesView,
  ChatView,
  ClarificationCard,
  ConfirmDialog,
  DailySummaryView,
  DemoDrawer,
  FileList,
  HistoryView,
  HomeView,
  LoginScreen,
  MemoryView,
  OrganizationPicker,
  PersonalCenterWindow,
  ProjectDialog,
  ScopePanel,
  Toast,
  UiIcon,
  WeeklyBriefView,
} from "./prototype-components";

export function DemoProductPrototype() {
  const [role, setRole] = useState<AuthRole>(null);
  const [themePreference, setThemePreference] = useState<ThemePreference>(() => {
    if (typeof window === "undefined") return "system";
    const savedTheme = window.localStorage.getItem("executive-workbench-theme");
    return savedTheme === "light" || savedTheme === "dark" || savedTheme === "system" ? savedTheme : "system";
  });
  const [languagePreference, setLanguagePreference] = useState<UiLanguage>(() => {
    if (typeof window === "undefined") return "zh-CN";
    const savedLanguage = window.localStorage.getItem("executive-workbench-language");
    return savedLanguage === "zh-TW" || savedLanguage === "en" || savedLanguage === "zh-CN" ? savedLanguage : "zh-CN";
  });
  const [mode, setMode] = useState<LoginMode>("executive");
  const [step, setStep] = useState<AuthStep>("login");
  const [account, setAccount] = useState("chairman");
  const [password, setPassword] = useState("Demo@2026");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const [pendingDestination, setPendingDestination] = useState<ExecutiveView>("home");
  const [pendingConversationId, setPendingConversationId] = useState<number | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = themePreference;
    document.documentElement.style.colorScheme = themePreference === "system" ? "light dark" : themePreference;
    window.localStorage.setItem("executive-workbench-theme", themePreference);
  }, [themePreference]);

  useEffect(() => {
    document.documentElement.lang = languagePreference;
    window.localStorage.setItem("executive-workbench-language", languagePreference);
  }, [languagePreference]);

  function switchMode(nextMode: LoginMode) {
    setMode(nextMode);
    setStep("login");
    setLoginError("");
    setAttempts(0);
    setLockedUntil(null);
    setAccount(nextMode === "executive" ? "chairman" : "admin");
    setPassword(nextMode === "executive" ? "Demo@2026" : "Admin@2026");
  }

  function handleLogin(event: FormEvent) {
    event.preventDefault();
    if (lockedUntil && lockedUntil > Date.now()) {
      setLoginError("尝试次数过多，请稍后再试或联系企业管理员。");
      return;
    }

    const expectedAccount = mode === "executive" ? "chairman" : "admin";
    const expectedPassword = mode === "executive" ? "Demo@2026" : "Admin@2026";
    if (account !== expectedAccount || password !== expectedPassword) {
      const nextAttempts = attempts + 1;
      setAttempts(nextAttempts);
      if (nextAttempts >= 3) {
        setLockedUntil(Date.now() + 30_000);
        setLoginError("尝试次数过多，请稍后再试或联系企业管理员。");
        window.setTimeout(() => {
          setLockedUntil(null);
          setAttempts(0);
          setLoginError("");
        }, 30_000);
      } else {
        setLoginError("账号或密码错误");
      }
      return;
    }

    setLoginError("");
    if (mode === "executive") {
      setStep("change-password");
      return;
    }
    setRole("admin");
  }

  function handlePasswordChange(event: FormEvent) {
    event.preventDefault();
    if (newPassword.length < 8 || !/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) {
      setLoginError("新密码至少 8 位，并同时包含字母和数字。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setLoginError("两次输入的新密码不一致。");
      return;
    }
    setLoginError("");
    const destination = new URLSearchParams(window.location.search).get("view");
    const conversationId = Number(new URLSearchParams(window.location.search).get("conversation"));
    setPendingDestination(destination === "daily" || destination === "weekly" ? destination : "home");
    setPendingConversationId(Number.isFinite(conversationId) && conversationId > 0 ? conversationId : null);
    setRole("executive");
  }

  function logout() {
    setRole(null);
    setStep("login");
    setMode("executive");
    setAccount("chairman");
    setPassword("Demo@2026");
    setNewPassword("");
    setConfirmPassword("");
    setLoginError("");
  }

  if (!role) {
    return (
      <LoginScreen
        mode={mode}
        step={step}
        account={account}
        password={password}
        newPassword={newPassword}
        confirmPassword={confirmPassword}
        error={loginError}
        locked={Boolean(lockedUntil)}
        onModeChange={switchMode}
        onAccountChange={setAccount}
        onPasswordChange={setPassword}
        onNewPasswordChange={setNewPassword}
        onConfirmPasswordChange={setConfirmPassword}
        onLogin={handleLogin}
        onChangePassword={handlePasswordChange}
        onBack={() => {
          setStep("login");
          setLoginError("");
        }}
      />
    );
  }

  if (role === "admin") {
    return <AdminWorkspace onLogout={logout} />;
  }

  return (
    <ExecutiveWorkspace
      initialView={pendingDestination}
      initialConversationId={pendingConversationId}
      themePreference={themePreference}
      onThemePreferenceChange={setThemePreference}
      languagePreference={languagePreference}
      onLanguagePreferenceChange={setLanguagePreference}
      onLogout={logout}
    />
  );
}

function ExecutiveWorkspace({
  initialView,
  initialConversationId,
  themePreference,
  onThemePreferenceChange,
  languagePreference,
  onLanguagePreferenceChange,
  onLogout,
}: {
  initialView: ExecutiveView;
  initialConversationId: number | null;
  themePreference: ThemePreference;
  onThemePreferenceChange: (theme: ThemePreference) => void;
  languagePreference: UiLanguage;
  onLanguagePreferenceChange: (language: UiLanguage) => void;
  onLogout: () => void;
}) {
  const linkedConversation = initialConversationId ? initialConversations.find((item) => item.id === initialConversationId) : undefined;
  const linkedPanel: WorkspacePanelView | null = linkedConversation?.type === "每日摘要" ? "daily" : linkedConversation?.type === "每周简报" ? "weekly" : null;
  const linkedRoute: RouteKind = linkedConversation?.type === "文件" ? "file" : linkedConversation?.type === "泛化" ? "research" : "data";
  const linkedAnswerId = linkedConversation?.type === "文件"
    ? "file"
    : linkedConversation?.type === "泛化"
      ? "research"
      : /回款|应收|现金/.test(linkedConversation?.title ?? "")
        ? "collection"
        : linkedConversation?.title.includes("项目")
          ? "delivery"
          : "overview";
  const linkedChat = Boolean(linkedConversation && !linkedPanel);
  const [view, setView] = useState<ExecutiveView>(linkedChat || initialView === "chat" ? "chat" : "home");
  const [activePanel, setActivePanel] = useState<WorkspacePanelView | null>(linkedPanel ?? (initialView !== "home" && initialView !== "chat" ? initialView : null));
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [homeQuestion, setHomeQuestion] = useState("");
  const [chatDraft, setChatDraft] = useState("");
  const [lastQuestion, setLastQuestion] = useState(linkedChat ? linkedConversation?.title ?? "" : "");
  const [previousQuestion, setPreviousQuestion] = useState("");
  const [chatStage, setChatStage] = useState<ChatStage>(linkedChat ? "ready" : "empty");
  const [routeKind, setRouteKind] = useState<RouteKind>(linkedRoute);
  const [activeAnswerId, setActiveAnswerId] = useState(linkedAnswerId);
  const [answerVersion, setAnswerVersion] = useState(1);
  const [chatTitle, setChatTitle] = useState(linkedChat ? linkedConversation?.title ?? "新会话" : "新会话");
  const [activeConversationId, setActiveConversationId] = useState<number | null>(linkedChat ? linkedConversation?.id ?? null : null);
  const [scope, setScope] = useState<ScopeState>({ time: "本月累计", organizationIds: [ALL_ORGANIZATIONS_ID], owner: "", object: "" });
  const [scopePanelOpen, setScopePanelOpen] = useState(false);
  const [files, setFiles] = useState<DemoFile[]>(linkedConversation?.type === "文件" ? [demoReadyFile()] : []);
  const [selectedFile, setSelectedFile] = useState<number | null>(null);
  const [conversations, setConversations] = useState(initialConversations);
  const [sidebarProjects, setSidebarProjects] = useState<SidebarProject[]>(initialSidebarProjects);
  const [memories, setMemories] = useState(initialMemories);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [languageMenuOpen, setLanguageMenuOpen] = useState(false);
  const [personalCenterView, setPersonalCenterView] = useState<PersonalCenterView | null>(null);
  const [executiveProfile, setExecutiveProfile] = useState<ExecutiveProfile>(() => {
    if (typeof window === "undefined") return initialExecutiveProfile;
    const savedProfile = window.localStorage.getItem("executive-workbench-profile");
    if (!savedProfile) return initialExecutiveProfile;
    try {
      return { ...initialExecutiveProfile, ...JSON.parse(savedProfile) } as ExecutiveProfile;
    } catch {
      return initialExecutiveProfile;
    }
  });
  const [conversationMenuOpen, setConversationMenuOpen] = useState(false);
  const [pinnedConversationIds, setPinnedConversationIds] = useState<number[]>([1, 2]);
  const [unreadConversationIds, setUnreadConversationIds] = useState<number[]>([]);
  const [archivedConversationIds, setArchivedConversationIds] = useState<number[]>([]);
  const [pinnedProjectIds, setPinnedProjectIds] = useState<string[]>([]);
  const [expandedProjectIds, setExpandedProjectIds] = useState<string[]>(["collection"]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [sidebarMenu, setSidebarMenu] = useState<SidebarMenuState | null>(null);
  const [projectDialog, setProjectDialog] = useState<ProjectDialogState | null>(null);
  const [sidebarRenameId, setSidebarRenameId] = useState<number | null>(null);
  const [sidebarRenameDraft, setSidebarRenameDraft] = useState("");
  const [renamingConversation, setRenamingConversation] = useState(false);
  const [titleDraft, setTitleDraft] = useState("新会话");
  const [demoOpen, setDemoOpen] = useState(false);
  const [feishuPreview, setFeishuPreview] = useState(false);
  const [clarificationRound, setClarificationRound] = useState<1 | 2>(1);
  const [clarificationOrganizations, setClarificationOrganizations] = useState<string[]>([]);
  const [clarificationOwner, setClarificationOwner] = useState("");
  const [inheritedNotice, setInheritedNotice] = useState("");
  const [memoryCandidate, setMemoryCandidate] = useState(false);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [toast, setToast] = useState("");
  const [online, setOnline] = useState(true);
  const [routeRecords, setRouteRecords] = useState<RouteRecord[]>([]);
  const [newTopicNotice, setNewTopicNotice] = useState(false);
  const timers = useRef<number[]>([]);
  const homeComposerRef = useRef<HTMLTextAreaElement>(null);
  const homeFileRef = useRef<HTMLInputElement>(null);
  const chatFileRef = useRef<HTMLInputElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const sidebarMenuRef = useRef<HTMLDivElement>(null);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  const copy = workbenchCopy[languagePreference];

  useEffect(() => {
    window.localStorage.setItem("executive-workbench-profile", JSON.stringify(executiveProfile));
  }, [executiveProfile]);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      timers.current.forEach((timer) => window.clearTimeout(timer));
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!sidebarMenu) return;
    window.requestAnimationFrame(() => sidebarMenuRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus());
    const closeMenu = (event: PointerEvent) => {
      if ((event.target as HTMLElement).closest("[data-sidebar-menu]")) return;
      setSidebarMenu(null);
    };
    const handleEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setSidebarMenu(null);
    };
    window.addEventListener("pointerdown", closeMenu);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("pointerdown", closeMenu);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [sidebarMenu]);

  useEffect(() => {
    if (!accountMenuOpen) return;
    const closeMenu = (event: PointerEvent) => {
      if (accountMenuRef.current?.contains(event.target as Node)) return;
      setAccountMenuOpen(false);
      setLanguageMenuOpen(false);
    };
    const handleEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (languageMenuOpen) setLanguageMenuOpen(false);
      else setAccountMenuOpen(false);
    };
    window.addEventListener("pointerdown", closeMenu);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("pointerdown", closeMenu);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [accountMenuOpen, languageMenuOpen]);

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k") return;
      event.preventDefault();
      timers.current.forEach((timer) => window.clearTimeout(timer));
      timers.current = [];
      setLastQuestion("");
      setPreviousQuestion("");
      setChatDraft("");
      setChatStage("empty");
      setRouteKind("data");
      setActiveAnswerId("overview");
      setAnswerVersion(1);
      setChatTitle("新会话");
      setActiveConversationId(null);
      setFiles([]);
      setScope({ time: "本月累计", organizationIds: [ALL_ORGANIZATIONS_ID], owner: "", object: "" });
      setInheritedNotice("");
      setMemoryCandidate(false);
      setNewTopicNotice(false);
      setActiveProjectId(null);
      setSidebarMenu(null);
      setSidebarRenameId(null);
      setActivePanel(null);
      setSidebarOpen(false);
      setView("home");
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (activePanel === "daily" || activePanel === "weekly") url.searchParams.set("view", activePanel);
    else url.searchParams.delete("view");
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
  }, [activePanel]);

  const networkUnavailable = !online;
  const visibleConversations = useMemo(
    () => conversations.filter((item) => !archivedConversationIds.includes(item.id)),
    [archivedConversationIds, conversations],
  );
  const pinnedConversations = useMemo(
    () => visibleConversations.filter((item) => pinnedConversationIds.includes(item.id)),
    [pinnedConversationIds, visibleConversations],
  );
  const recentConversations = useMemo(
    () => visibleConversations.filter((item) => !pinnedConversationIds.includes(item.id)).slice(0, 5),
    [pinnedConversationIds, visibleConversations],
  );
  const orderedSidebarProjects = useMemo(
    () => [...sidebarProjects].sort((first, second) => {
      const firstPinned = pinnedProjectIds.includes(first.id) ? 1 : 0;
      const secondPinned = pinnedProjectIds.includes(second.id) ? 1 : 0;
      return secondPinned - firstPinned;
    }),
    [pinnedProjectIds, sidebarProjects],
  );

  function clearTimers() {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current = [];
  }

  function notify(message: string) {
    setToast(message);
  }

  function openSidebarMenu(
    event: ReactMouseEvent<HTMLButtonElement>,
    target: { kind: "conversation"; conversationId: number } | { kind: "project"; projectId: string },
  ) {
    event.stopPropagation();
    const sidebarBounds = sidebarRef.current?.getBoundingClientRect();
    const triggerBounds = event.currentTarget.getBoundingClientRect();
    const desiredTop = sidebarBounds ? triggerBounds.top - sidebarBounds.top - 8 : triggerBounds.top;
    const menuHeight = target.kind === "project" ? 198 : 338;
    const maxTop = Math.max(78, window.innerHeight - menuHeight);
    setSidebarMenu((current) => {
      const sameTarget = current?.kind === target.kind
        && (target.kind === "conversation"
          ? current.kind === "conversation" && current.conversationId === target.conversationId
          : current.kind === "project" && current.projectId === target.projectId);
      return sameTarget ? null : { ...target, top: Math.min(Math.max(desiredTop, 78), maxTop) };
    });
  }

  function toggleUnread(conversationId: number) {
    setUnreadConversationIds((current) => current.includes(conversationId)
      ? current.filter((id) => id !== conversationId)
      : [...current, conversationId]);
    setSidebarMenu(null);
    notify(unreadConversationIds.includes(conversationId) ? "已标记为已读" : "已标记为未读");
  }

  function togglePinnedConversation(conversationId: number) {
    const currentlyPinned = pinnedConversationIds.includes(conversationId);
    setPinnedConversationIds((current) => currentlyPinned
      ? current.filter((id) => id !== conversationId)
      : [...current, conversationId]);
    setSidebarMenu(null);
    notify(currentlyPinned ? "已取消置顶" : "已置顶");
  }

  function beginSidebarRename(item: ConversationItem) {
    setSidebarRenameId(item.id);
    setSidebarRenameDraft(item.title);
    setSidebarMenu(null);
  }

  function saveSidebarRename(event: FormEvent, conversationId: number) {
    event.preventDefault();
    renameConversation(conversationId, sidebarRenameDraft);
    setSidebarRenameId(null);
    setSidebarRenameDraft("");
  }

  function requestArchiveConversation(item: ConversationItem) {
    setSidebarMenu(null);
    setConfirmState({
      title: `归档会话“${item.title}”？`,
      description: "归档后，这条会话将从置顶、项目和最近列表中隐藏，仍可在历史会话中搜索。",
      confirmLabel: "归档会话",
      action: () => {
        setArchivedConversationIds((current) => current.includes(item.id) ? current : [...current, item.id]);
        setPinnedConversationIds((current) => current.filter((id) => id !== item.id));
        setUnreadConversationIds((current) => current.filter((id) => id !== item.id));
        notify(`“${item.title}”已归档，可在历史会话中搜索`);
      },
    });
  }

  function copyConversationId(item: ConversationItem) {
    setSidebarMenu(null);
    void copyToClipboard(`conversation_${item.id}`, notify, "会话 ID 已复制");
  }

  function copyConversationDeepLink(item: ConversationItem) {
    const url = new URL(window.location.href);
    url.searchParams.delete("view");
    url.searchParams.set("conversation", String(item.id));
    setSidebarMenu(null);
    void copyToClipboard(url.toString(), notify, "会话深度链接已复制");
  }

  function continueInNewConversation(item: ConversationItem) {
    clearTimers();
    setActiveProjectId(null);
    setActiveConversationId(null);
    setActivePanel(null);
    setSidebarMenu(null);
    setSidebarOpen(false);
    setView("chat");
    setChatStage("empty");
    setChatTitle("新会话");
    setLastQuestion("");
    setPreviousQuestion(item.title);
    setChatDraft(`继续分析：${item.title}`);
    setInheritedNotice(`已从“${item.title}”继承经营上下文，原会话保持不变。`);
    notify("已在新会话中继承上下文");
  }

  function toggleProject(projectId: string) {
    setExpandedProjectIds((current) => current.includes(projectId)
      ? current.filter((id) => id !== projectId)
      : [...current, projectId]);
  }

  function startProjectConversation(project: SidebarProject) {
    resetConversation();
    setActiveProjectId(project.id);
    setExpandedProjectIds((current) => current.includes(project.id) ? current : [...current, project.id]);
    notify(`新会话将保存到“${project.title}”`);
    window.requestAnimationFrame(() => homeComposerRef.current?.focus());
  }

  function togglePinnedProject(project: SidebarProject) {
    const currentlyPinned = pinnedProjectIds.includes(project.id);
    setPinnedProjectIds((current) => currentlyPinned
      ? current.filter((id) => id !== project.id)
      : [project.id, ...current]);
    setSidebarMenu(null);
    notify(currentlyPinned ? `已取消置顶“${project.title}”` : `已置顶“${project.title}”`);
  }

  function saveProject(
    dialogState: ProjectDialogState,
    title: string,
    description: string,
  ): string | null {
    const normalizedTitle = title.trim();
    const duplicate = sidebarProjects.some((project) => (
      project.title.toLocaleLowerCase() === normalizedTitle.toLocaleLowerCase()
      && (dialogState.mode === "create" || project.id !== dialogState.projectId)
    ));
    if (duplicate) return "已有同名项目，请使用其他名称。";

    if (dialogState.mode === "create") {
      const id = `project-${Date.now()}`;
      setSidebarProjects((current) => [...current, { id, title: normalizedTitle, description: description.trim(), conversationIds: [] }]);
      setExpandedProjectIds((current) => [...current, id]);
      setProjectDialog(null);
      notify(`项目“${normalizedTitle}”已创建`);
      return null;
    }

    setSidebarProjects((current) => current.map((project) => project.id === dialogState.projectId
      ? { ...project, title: normalizedTitle, description: description.trim() }
      : project));
    setProjectDialog(null);
    notify("项目设置已更新");
    return null;
  }

  function requestArchiveProjectTasks(project: SidebarProject) {
    const activeConversationIds = project.conversationIds.filter((id) => !archivedConversationIds.includes(id));
    setSidebarMenu(null);
    if (!activeConversationIds.length) {
      notify("这个项目没有可归档的任务");
      return;
    }
    setConfirmState({
      title: `归档“${project.title}”中的任务？`,
      description: `${activeConversationIds.length} 条任务将从侧栏和最近会话中隐藏，项目本身会保留，任务仍可在历史会话中搜索。`,
      confirmLabel: "归档任务",
      action: () => {
        setArchivedConversationIds((current) => Array.from(new Set([...current, ...activeConversationIds])));
        setPinnedConversationIds((current) => current.filter((id) => !activeConversationIds.includes(id)));
        setUnreadConversationIds((current) => current.filter((id) => !activeConversationIds.includes(id)));
        notify(`“${project.title}”中的 ${activeConversationIds.length} 条任务已归档`);
      },
    });
  }

  function requestRemoveProject(project: SidebarProject) {
    setSidebarMenu(null);
    const retainedConversationCount = project.conversationIds.length;
    setConfirmState({
      title: `移除项目“${project.title}”？`,
      description: retainedConversationCount
        ? `只会移除项目分组，其中 ${retainedConversationCount} 条会话仍保留在最近或历史会话中。若要恢复分组，需要重新创建项目。`
        : "这个空项目将从侧栏移除。若要恢复，需要重新创建项目。",
      confirmLabel: "移除项目",
      tone: "danger",
      action: () => {
        setSidebarProjects((current) => current.filter((item) => item.id !== project.id));
        setPinnedProjectIds((current) => current.filter((id) => id !== project.id));
        setExpandedProjectIds((current) => current.filter((id) => id !== project.id));
        setActiveProjectId((current) => current === project.id ? null : current);
        notify(`项目“${project.title}”已移除，会话仍然保留`);
      },
    });
  }

  function switchView(nextView: ExecutiveView) {
    setActiveProjectId(null);
    setAccountMenuOpen(false);
    setLanguageMenuOpen(false);
    setConversationMenuOpen(false);
    setSidebarOpen(false);
    if (nextView === "home" || nextView === "chat") {
      setActivePanel(null);
      setView(nextView);
      if (nextView === "chat" && !lastQuestion) setChatStage("empty");
      return;
    }
    setActivePanel(nextView);
  }

  function resetConversation() {
    clearTimers();
    setLastQuestion("");
    setPreviousQuestion("");
    setChatDraft("");
    setChatStage("empty");
    setRouteKind("data");
    setActiveAnswerId("overview");
    setAnswerVersion(1);
    setChatTitle("新会话");
    setActiveConversationId(null);
    setFiles([]);
    setScope({ time: "本月累计", organizationIds: [ALL_ORGANIZATIONS_ID], owner: "", object: "" });
    setInheritedNotice("");
    setMemoryCandidate(false);
    setNewTopicNotice(false);
    setActiveProjectId(null);
    setSidebarMenu(null);
    setSidebarRenameId(null);
    setActivePanel(null);
    setSidebarOpen(false);
    setView("home");
  }

  function classifyQuestion(question: string): { route: RouteKind; answerId: string } {
    if (/这份|文件|报告里|刚才上传|工作表|幻灯片/.test(question)) return { route: "file", answerId: "file" };
    if (/搜索|公开|行业|竞争对手|竞品|市场/.test(question)) return { route: "research", answerId: "research" };
    if (/写|整理|备忘录|邮件|讲话|会议总结|汇报/.test(question)) return { route: "general", answerId: "general" };
    if (/延期.*回款|项目.*回款|回款.*项目|哪些项目可能延期/.test(question)) return { route: "data", answerId: "delivery" };
    if (/回款|应收|现金/.test(question)) return { route: "data", answerId: "collection" };
    if (/负责人|事业部|部门|谁的|谁最好|谁风险|谁.*推进|华东|华南|北区/.test(question)) return { route: "data", answerId: "organization" };
    if (/预测|大概能签|能签多少/.test(question)) return { route: "data", answerId: "forecast" };
    if (/重点客户|客户现在/.test(question)) return { route: "data", answerId: "customers" };
    if (/为什么|原因|下降|变化/.test(question)) return { route: "data", answerId: "change" };
    if (/目标|完成多少|差距/.test(question)) return { route: "data", answerId: "target" };
    if (/项目|交付|里程碑/.test(question)) return { route: "data", answerId: "delivery" };
    return { route: "data", answerId: "overview" };
  }

  function addRouteRecord(route: RouteKind, summary: string, status: RouteRecord["status"]) {
    setRouteRecords((current) => [
      { id: Date.now(), time: "刚刚", route, summary, status },
      ...current,
    ].slice(0, 12));
  }

  function startProcessing(
    question: string,
    options?: { route?: RouteKind; answerId?: string; clarify?: boolean; preserveContext?: boolean; retry?: boolean },
  ) {
    const finalQuestion = question.trim();
    if (!finalQuestion) return;
    clearTimers();
    const classified = options?.route && options.answerId
      ? { route: options.route, answerId: options.answerId }
      : classifyQuestion(finalQuestion);

    if (lastQuestion && !options?.preserveContext) setPreviousQuestion(lastQuestion);
    setLastQuestion(finalQuestion);
    setChatDraft("");
    setHomeQuestion("");
    setRouteKind(classified.route);
    setActiveAnswerId(classified.answerId);
    setAnswerVersion((current) => options?.retry ? current + 1 : 1);
    setMemoryCandidate(/以后|默认|先给我结论/.test(finalQuestion));
    setNewTopicNotice(Boolean(lastQuestion && classified.route !== routeKind));
    setActivePanel(null);
    setSidebarOpen(false);
    setView("chat");
    const nextConversationTitle = makeConversationTitle(finalQuestion, classified.answerId);
    setChatTitle(nextConversationTitle);

    if (activeProjectId && sidebarProjects.some((project) => project.id === activeProjectId)) {
      const conversationId = Date.now();
      const taskTitle = makeTaskTitle(finalQuestion);
      const conversationType: ConversationItem["type"] = classified.route === "file"
        ? "文件"
        : classified.route === "research"
          ? "泛化"
          : "数据";
      setConversations((current) => [{
        id: conversationId,
        title: taskTitle,
        preview: finalQuestion.length > 46 ? `${finalQuestion.slice(0, 46)}…` : finalQuestion,
        question: finalQuestion,
        route: classified.route,
        answerId: classified.answerId,
        time: "刚刚",
        group: "今天",
        type: conversationType,
        searchable: `${taskTitle} ${finalQuestion}`,
      }, ...current]);
      setSidebarProjects((current) => current.map((project) => project.id === activeProjectId
        ? { ...project, conversationIds: [conversationId, ...project.conversationIds] }
        : project));
      setExpandedProjectIds((current) => current.includes(activeProjectId) ? current : [...current, activeProjectId]);
      setActiveConversationId(conversationId);
      setActiveProjectId(null);
    }

    const requiresClarification = options?.clarify || /谁(?:的商机)?推进最慢|谁最好|谁风险最大/.test(finalQuestion);
    if (requiresClarification) {
      setClarificationRound(1);
      setClarificationOrganizations([]);
      setClarificationOwner("");
      setChatStage("clarifying");
      addRouteRecord(classified.route, "负责人表现，需要补充组织范围", "待补充范围");
      return;
    }

    if (networkUnavailable) {
      setChatStage("offline");
      addRouteRecord(classified.route, safeRouteSummary(classified.route), "待网络确认");
      return;
    }

    addRouteRecord(classified.route, safeRouteSummary(classified.route), "已路由");
    setChatStage("understanding");
    timers.current.push(
      window.setTimeout(() => setChatStage("working"), 520),
      window.setTimeout(() => setChatStage("composing"), 1120),
      window.setTimeout(() => setChatStage("ready"), 1760),
    );
  }

  function confirmClarification() {
    if (clarificationRound === 1) {
      if (!clarificationOrganizations.length) {
        notify("请选择至少一个组织范围");
        return;
      }
      setClarificationRound(2);
      return;
    }
    if (!clarificationOwner) {
      notify("请选择一名负责人或全部负责人");
      return;
    }
    setScope({
      time: "本月累计",
      organizationIds: clarificationOrganizations,
      owner: clarificationOwner === "全部负责人" ? "" : clarificationOwner,
      object: "商机推进",
    });
    addRouteRecord("data", "负责人商机推进，范围已确认", "已路由");
    setChatStage("understanding");
    setActiveAnswerId("people");
    setChatTitle("负责人商机推进对比");
    timers.current.push(
      window.setTimeout(() => setChatStage("working"), 420),
      window.setTimeout(() => setChatStage("composing"), 980),
      window.setTimeout(() => setChatStage("ready"), 1540),
    );
  }

  function retryCurrent() {
    startProcessing(lastQuestion, { route: routeKind, answerId: activeAnswerId, preserveContext: true, retry: true });
  }

  function stopCurrent() {
    clearTimers();
    setChatStage("stopped");
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>, source: "home" | "chat") {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      startProcessing(source === "home" ? homeQuestion : chatDraft);
    }
  }

  function chooseSuggestion(suggestion: string, source: "home" | "chat") {
    if (source === "home") {
      setHomeQuestion(suggestion);
      window.requestAnimationFrame(() => homeComposerRef.current?.focus());
    } else {
      setChatDraft(suggestion);
      notify("问题已放入输入框，可修改后发送");
    }
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>, fromHome: boolean) {
    const incoming = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!incoming.length) return;
    if ((fromHome ? 0 : files.length) + incoming.length > 10) {
      notify("单个会话最多上传 10 个文件");
      return;
    }

    const nextFiles: DemoFile[] = incoming.map((file, index) => {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      const supported = ["pdf", "docx", "xlsx", "pptx"].includes(extension);
      const tooLarge = file.size > 50 * 1024 * 1024;
      return {
        id: Date.now() + index,
        name: file.name,
        kind: extension.toUpperCase() || "未知",
        size: formatFileSize(file.size),
        status: !supported || tooLarge ? "解析失败" : "上传中",
        uploadedAt: "刚刚",
        range: supported ? fileRange(extension) : "未读取",
        error: !supported ? "格式不支持。请上传 PDF、DOCX、XLSX 或 PPTX。" : tooLarge ? "文件超过 50 MB 上限。" : undefined,
      };
    });
    setFiles((current) => fromHome ? nextFiles : [...current, ...nextFiles]);
    setRouteKind("file");
    setChatTitle("当前会话文件");
    if (fromHome) {
      setActivePanel(null);
      setView("chat");
      setChatStage("empty");
    }
    notify(`${incoming.length} 个文件已加入当前会话`);

    nextFiles.forEach((item) => {
      if (item.status === "解析失败") return;
      timers.current.push(
        window.setTimeout(() => updateFileStatus(item.id, "等待解析"), 320),
        window.setTimeout(() => updateFileStatus(item.id, "解析中"), 760),
        window.setTimeout(() => {
          if (/扫描|scan/i.test(item.name)) {
            setFiles((current) => current.map((file) => file.id === item.id ? { ...file, status: "解析失败", error: "文件主要由扫描图片组成，首版暂不支持 OCR。" } : file));
          } else {
            updateFileStatus(item.id, "可使用");
          }
        }, 1550),
      );
    });
  }

  function updateFileStatus(id: number, status: DemoFile["status"]) {
    setFiles((current) => current.map((file) => file.id === id ? { ...file, status } : file));
  }

  function requestDeleteFile(file: DemoFile) {
    setConfirmState({
      title: `删除《${file.name}》？`,
      description: "删除后，原文件、解析文本和检索索引将无法在本会话继续使用。历史回答文字会保留，并标记来源文件已删除。",
      confirmLabel: "删除文件",
      tone: "danger",
      action: () => {
        setFiles((current) => current.filter((item) => item.id !== file.id));
        setSelectedFile(null);
        notify("文件及其解析内容已删除");
      },
    });
  }

  function openConversation(item: ConversationItem) {
    setActiveProjectId(null);
    setActiveConversationId(item.id);
    setUnreadConversationIds((current) => current.filter((id) => id !== item.id));
    setSidebarMenu(null);
    if (item.type === "每日摘要") {
      setActivePanel("daily");
      setSidebarOpen(false);
      return;
    }
    if (item.type === "每周简报") {
      setActivePanel("weekly");
      setSidebarOpen(false);
      return;
    }
    const route: RouteKind = item.route ?? (item.type === "文件" ? "file" : item.type === "泛化" ? "research" : "data");
    const answerId = item.answerId ?? (item.type === "文件"
      ? "file"
      : item.type === "泛化"
        ? "research"
        : /回款|应收|现金/.test(item.title)
          ? "collection"
          : item.title.includes("项目")
            ? "delivery"
            : "overview");
    setChatTitle(item.title);
    setLastQuestion(item.question ?? item.title);
    setPreviousQuestion("");
    setRouteKind(route);
    setActiveAnswerId(answerId);
    setChatStage("ready");
    if (item.type === "文件" && !files.length) {
      setFiles([demoReadyFile()]);
    }
    setActivePanel(null);
    setSidebarOpen(false);
    setView("chat");
  }

  function renameConversation(id: number, title: string) {
    const nextTitle = title.trim();
    if (!nextTitle) return;
    setConversations((current) => current.map((item) => item.id === id ? { ...item, title: nextTitle } : item));
    if (activeConversationId === id) setChatTitle(nextTitle);
    notify("会话标题已修改");
  }

  function requestDeleteConversation(item: ConversationItem) {
    setConfirmState({
      title: `删除会话“${item.title}”？`,
      description: "会话消息和当前会话附件将删除。由该会话产生的长期记忆不会自动删除。",
      confirmLabel: "删除会话",
      tone: "danger",
      action: () => {
        setConversations((current) => current.filter((conversation) => conversation.id !== item.id));
        setSidebarProjects((current) => current.map((project) => ({
          ...project,
          conversationIds: project.conversationIds.filter((id) => id !== item.id),
        })));
        setPinnedConversationIds((current) => current.filter((id) => id !== item.id));
        setUnreadConversationIds((current) => current.filter((id) => id !== item.id));
        setArchivedConversationIds((current) => current.filter((id) => id !== item.id));
        if (activeConversationId === item.id) resetConversation();
        notify("会话已删除");
      },
    });
  }

  function saveMemory(memory: MemoryItem) {
    setMemories((current) => {
      const exists = current.some((item) => item.id === memory.id);
      return exists ? current.map((item) => item.id === memory.id ? memory : item) : [memory, ...current];
    });
    notify("记忆已保存，将用于后续新消息");
  }

  function requestDeleteMemory(memory: MemoryItem) {
    setConfirmState({
      title: "删除这条长期记忆？",
      description: `“${memory.content}”删除后将立即停止使用，历史回答不会改变。`,
      confirmLabel: "删除记忆",
      tone: "danger",
      action: () => {
        setMemories((current) => current.filter((item) => item.id !== memory.id));
        notify("记忆已删除，后续消息不再使用");
      },
    });
  }

  function requestClearMemories() {
    setConfirmState({
      title: "清空全部长期记忆？",
      description: "清空后，系统将不再记得您的长期偏好和默认口径。历史会话不会因此删除。",
      confirmLabel: "确认清空",
      tone: "danger",
      action: () => {
        setMemories([]);
        notify("长期记忆已清空");
      },
    });
  }

  function saveMemoryCandidate() {
    const exists = memories.some((memory) => memory.content.includes("金额统一使用万元"));
    if (!exists) {
      setMemories((current) => [{ id: Date.now(), content: "金额统一使用万元，回答先给结论。", category: "表达与数字偏好", createdAt: "刚刚", usedAt: "尚未使用", source: chatTitle }, ...current]);
    }
    setMemoryCandidate(false);
    notify("偏好已保存，可在记忆页修改或删除");
  }

  function runDemoScenario(id: number) {
    setActiveProjectId(null);
    setActiveConversationId(null);
    setDemoOpen(false);
    if (id === 1) {
      setActivePanel(null);
      setView("home");
      return;
    }
    if (id === 2) {
      startProcessing("这个月整体经营怎么样？", { route: "data", answerId: "overview" });
      return;
    }
    if (id === 3) {
      startProcessing("谁的商机推进最慢？", { route: "data", answerId: "organization", clarify: true });
      return;
    }
    if (id === 4) {
      setScope({ time: "本月累计", organizationIds: ["east"], owner: "", object: "商机" });
      setInheritedNotice("已继承上一轮的本月与商机口径，仅将组织范围改为华东事业部。");
      startProcessing("华东呢？", { route: "data", answerId: "organization", preserveContext: true });
      return;
    }
    if (id === 5) {
      startProcessing("哪些项目可能延期，而且还有回款没完成？", { route: "data", answerId: "delivery" });
      return;
    }
    if (id === 6) {
      setFiles([demoReadyFile()]);
      startProcessing("这份报告提到的三个主要问题是什么？", { route: "file", answerId: "file" });
      return;
    }
    if (id === 7) {
      startProcessing("搜索一下这个行业最近三个月的重要变化，并说明可能对我们有什么影响。", { route: "research", answerId: "research" });
      return;
    }
    if (id === 8) {
      startProcessing("本月回款多少？", { route: "failure", answerId: "failure" });
      return;
    }
    if (id === 9) {
      setMemoryCandidate(true);
      startProcessing("以后金额默认用万元，先给我结论。", { route: "general", answerId: "general" });
      return;
    }
    setFeishuPreview(true);
    setActivePanel("daily");
  }

  function openPersonalCenter(nextView: PersonalCenterView) {
    setActiveProjectId(null);
    setAccountMenuOpen(false);
    setLanguageMenuOpen(false);
    setActivePanel(null);
    setPersonalCenterView(nextView);
  }

  function changeLanguage(nextLanguage: UiLanguage) {
    onLanguagePreferenceChange(nextLanguage);
    setLanguageMenuOpen(false);
    setAccountMenuOpen(false);
    const label = languageOptions.find((option) => option.id === nextLanguage)?.label ?? nextLanguage;
    notify(`界面语言已切换为 ${label}`);
  }

  function updateOrganizations(organizationIds: string[]) {
    setScope((current) => ({ ...current, organizationIds }));
    notify("事业部范围已更新，将用于后续问题");
  }

  const activeDataAnswer = answerConfigs[activeAnswerId] ?? answerConfigs.overview;
  const workspaceTitle = view === "home" ? "新会话" : chatTitle;
  const workspaceSubtitle = view === "home"
    ? "数据已更新至 7月25日 02:06"
    : routeKind === "file"
      ? `${files.length} 个当前会话文件`
      : `${scope.time} · ${formatOrganizationSelection(scope.organizationIds, languagePreference)}`;
  const panelTitle: Record<WorkspacePanelView, string> = {
    history: copy.navigation.history,
    memory: copy.navigation.memory,
    daily: copy.navigation.daily,
    weekly: copy.navigation.weekly,
    capabilities: "可查询范围",
    account: "账号与推送",
  };
  const sidebarMenuConversation = sidebarMenu?.kind === "conversation"
    ? conversations.find((item) => item.id === sidebarMenu.conversationId) ?? null
    : null;
  const sidebarMenuProject = sidebarMenu?.kind === "project"
    ? sidebarProjects.find((project) => project.id === sidebarMenu.projectId) ?? null
    : null;
  const reportPanelOpen = activePanel === "daily" || activePanel === "weekly";

  return (
    <div className={`product-shell workbench-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${sidebarOpen ? "sidebar-open" : ""}`} data-route-record-count={routeRecords.length}>
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      {networkUnavailable && (
        <div className="network-banner" role="status">
          <span>网络连接已中断。未确认送达的消息会保留，不会重复创建任务。</span>
        </div>
      )}
      <aside ref={sidebarRef} className="workspace-sidebar" aria-label="工作台侧栏">
        <header className="sidebar-brand-row">
          <button className="sidebar-brand" type="button" onClick={resetConversation} aria-label="打开新会话">
            <span className="brand-glyph" aria-hidden="true">董</span>
            <span className="sidebar-label"><strong>{copy.brand}</strong><small>{copy.brandSubtitle}</small></span>
          </button>
          <button className="sidebar-collapse" type="button" aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"} onClick={() => setSidebarCollapsed((current) => !current)}>{sidebarCollapsed ? "›" : "‹"}</button>
        </header>

        <div className="sidebar-scroll-region">
          <button className="new-conversation-button" type="button" onClick={resetConversation}>
            <span aria-hidden="true">＋</span><strong className="sidebar-label">{copy.newConversation}</strong><kbd className="sidebar-label">⌘ K</kbd>
          </button>

          <nav className="workspace-navigation" aria-label="经营工作台功能">
            {workspaceNavigation.map((item) => (
              <button type="button" key={item.id} className={activePanel === item.id ? "active" : ""} aria-current={activePanel === item.id ? "page" : undefined} onClick={() => switchView(item.id)}>
                <span aria-hidden="true">{item.short}</span><strong className="sidebar-label">{copy.navigation[item.id]}</strong>
              </button>
            ))}
          </nav>

          <div className="sidebar-sections">
            <section className="sidebar-section" aria-labelledby="sidebar-pinned-title">
              <header className="sidebar-section-header"><span id="sidebar-pinned-title">{copy.pinned}</span></header>
              <div className="sidebar-list">
                {pinnedConversations.map((item) => (
                  <div className="sidebar-row-shell" key={item.id}>
                    {sidebarRenameId === item.id ? (
                      <form className="sidebar-rename-form" onSubmit={(event) => saveSidebarRename(event, item.id)}>
                        <input value={sidebarRenameDraft} maxLength={28} onChange={(event) => setSidebarRenameDraft(event.target.value)} aria-label="新的会话名称" autoFocus />
                        <button type="submit" aria-label="保存名称">✓</button>
                        <button type="button" aria-label="取消重命名" onClick={() => setSidebarRenameId(null)}>×</button>
                      </form>
                    ) : (
                      <>
                        <button type="button" className={`sidebar-conversation-button ${view === "chat" && activeConversationId === item.id ? "active" : ""}`} onClick={() => openConversation(item)}>
                          <span className={`sidebar-unread-dot ${unreadConversationIds.includes(item.id) ? "visible" : ""}`} aria-hidden="true" />
                          <strong>{item.title}</strong>
                        </button>
                        <button type="button" className="sidebar-row-menu-button" data-sidebar-menu aria-label={`打开“${item.title}”操作菜单`} aria-haspopup="menu" aria-expanded={sidebarMenu?.kind === "conversation" && sidebarMenu.conversationId === item.id} onClick={(event) => openSidebarMenu(event, { kind: "conversation", conversationId: item.id })}>•••</button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section className="sidebar-section" aria-labelledby="sidebar-projects-title">
              <header className="sidebar-section-header"><span id="sidebar-projects-title">{copy.projects}</span><button type="button" className="sidebar-add-project" aria-label="新建项目" onClick={() => setProjectDialog({ mode: "create" })}>＋</button></header>
              <div className="sidebar-list sidebar-project-list">
                {orderedSidebarProjects.map((project) => {
                  const expanded = expandedProjectIds.includes(project.id);
                  const pinned = pinnedProjectIds.includes(project.id);
                  const projectConversations = project.conversationIds
                    .map((conversationId) => conversations.find((conversation) => conversation.id === conversationId))
                    .filter((conversation): conversation is ConversationItem => Boolean(conversation))
                    .filter((conversation) => !archivedConversationIds.includes(conversation.id));
                  return (
                    <div className={`sidebar-project ${pinned ? "pinned" : ""}`} key={project.id}>
                      <div className="sidebar-project-row-shell">
                        <button type="button" className="sidebar-project-button" aria-expanded={expanded} title={project.description || project.title} onClick={() => toggleProject(project.id)}>
                          <span className="sidebar-disclosure" aria-hidden="true">{expanded ? "⌄" : "›"}</span>
                          <span className="sidebar-project-mark" aria-hidden="true" />
                          <strong>{project.title}</strong>
                        </button>
                        <button type="button" className="sidebar-row-menu-button sidebar-project-menu-button" data-sidebar-menu aria-label={`打开“${project.title}”项目菜单`} aria-haspopup="menu" aria-expanded={sidebarMenu?.kind === "project" && sidebarMenu.projectId === project.id} onClick={(event) => openSidebarMenu(event, { kind: "project", projectId: project.id })}>•••</button>
                      </div>
                      {expanded && (
                        <div className="sidebar-project-conversations">
                          {projectConversations.map((conversation) => (
                            <button type="button" key={conversation.id} className={view === "chat" && activeConversationId === conversation.id ? "active" : ""} onClick={() => openConversation(conversation)}>
                              <span aria-hidden="true" />
                              <strong>{conversation.title}</strong>
                            </button>
                          ))}
                          <button type="button" className={`sidebar-project-start-button ${activeProjectId === project.id ? "active" : ""}`} onClick={() => startProjectConversation(project)}>
                            <span aria-hidden="true">＋</span>
                            <strong>{activeProjectId === project.id ? "等待输入第一个问题" : "在此项目新建会话"}</strong>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="sidebar-section" aria-labelledby="sidebar-recent-title">
              <header className="sidebar-section-header"><span id="sidebar-recent-title">{copy.recent}</span><button type="button" onClick={() => switchView("history")}>{copy.all}</button></header>
              <div className="sidebar-list">
                {recentConversations.map((item) => (
                  <div className="sidebar-row-shell" key={item.id}>
                    {sidebarRenameId === item.id ? (
                      <form className="sidebar-rename-form" onSubmit={(event) => saveSidebarRename(event, item.id)}>
                        <input value={sidebarRenameDraft} maxLength={28} onChange={(event) => setSidebarRenameDraft(event.target.value)} aria-label="新的会话名称" autoFocus />
                        <button type="submit" aria-label="保存名称">✓</button>
                        <button type="button" aria-label="取消重命名" onClick={() => setSidebarRenameId(null)}>×</button>
                      </form>
                    ) : (
                      <>
                        <button type="button" className={`sidebar-conversation-button ${view === "chat" && activeConversationId === item.id ? "active" : ""}`} onClick={() => openConversation(item)}>
                          <span className={`sidebar-unread-dot ${unreadConversationIds.includes(item.id) ? "visible" : ""}`} aria-hidden="true" />
                          <strong>{item.title}</strong>
                        </button>
                        <button type="button" className="sidebar-row-menu-button" data-sidebar-menu aria-label={`打开“${item.title}”操作菜单`} aria-haspopup="menu" aria-expanded={sidebarMenu?.kind === "conversation" && sidebarMenu.conversationId === item.id} onClick={(event) => openSidebarMenu(event, { kind: "conversation", conversationId: item.id })}>•••</button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>

        <footer className="sidebar-footer">
          <button type="button" className="sidebar-data-status" onClick={() => switchView("capabilities")}>
            <span className="status-dot positive" aria-hidden="true" /><span className="sidebar-label"><strong>{copy.dataAvailable}</strong><small>{copy.updatedAt}</small></span>
          </button>
          <div ref={accountMenuRef} className="profile-control workspace-profile">
            <button className="profile-button" type="button" aria-label="打开个人菜单" aria-expanded={accountMenuOpen} onClick={() => { setAccountMenuOpen((current) => !current); setLanguageMenuOpen(false); }}>
              <span className="profile-avatar" aria-hidden="true">RZ</span><span className="sidebar-label"><strong>{copy.role}</strong><small>{formatOrganizationSelection(scope.organizationIds, languagePreference, true)}</small></span><span className="profile-menu-chevron sidebar-label" aria-hidden="true">{accountMenuOpen ? "⌄" : "›"}</span>
            </button>
            {accountMenuOpen && (
              <div className="profile-menu account-menu" role="menu" aria-label="个人菜单">
                <button type="button" className="account-menu-identity" role="menuitem" onClick={() => openPersonalCenter("profile")}>
                  <span className="account-menu-avatar" aria-hidden="true">RZ</span>
                  <span><strong>{executiveProfile.displayName}</strong><small>{copy.role} · {formatOrganizationSelection(scope.organizationIds, languagePreference, true)}</small></span>
                  <UiIcon name="chevron" />
                </button>
                <div className="profile-menu-divider" />
                <button type="button" className="account-menu-item" role="menuitem" onClick={() => openPersonalCenter("appearance")}><UiIcon name="settings" /><span>{copy.settings}</span></button>
                <div className="account-language-control">
                  <button type="button" className="account-menu-item" role="menuitem" aria-haspopup="menu" aria-expanded={languageMenuOpen} onClick={() => setLanguageMenuOpen((current) => !current)}>
                    <UiIcon name="language" /><span>{copy.language}</span><small>{languageOptions.find((option) => option.id === languagePreference)?.label}</small><UiIcon name="chevron" />
                  </button>
                  {languageMenuOpen && (
                    <div className="language-submenu" role="menu" aria-label="选择界面语言">
                      {languageOptions.map((option) => (
                        <button type="button" key={option.id} role="menuitemradio" aria-checked={languagePreference === option.id} className={languagePreference === option.id ? "selected" : ""} onClick={() => changeLanguage(option.id)}>
                          <span>{option.label}</span><span aria-hidden="true">{languagePreference === option.id ? "✓" : ""}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="profile-menu-divider" />
                <button type="button" className="account-menu-item account-menu-logout" role="menuitem" onClick={onLogout}><UiIcon name="logout" /><span>{copy.logout}</span></button>
              </div>
            )}
          </div>
        </footer>

        {sidebarMenu && sidebarMenuConversation && (
          <div ref={sidebarMenuRef} className="sidebar-context-menu" data-sidebar-menu role="menu" aria-label={`“${sidebarMenuConversation.title}”会话操作`} style={{ top: sidebarMenu.top }}>
            <button type="button" role="menuitem" onClick={() => togglePinnedConversation(sidebarMenuConversation.id)}>{pinnedConversationIds.includes(sidebarMenuConversation.id) ? "取消置顶" : "置顶"}</button>
            <button type="button" role="menuitem" onClick={() => toggleUnread(sidebarMenuConversation.id)}>{unreadConversationIds.includes(sidebarMenuConversation.id) ? "标记为已读" : "标记未读"}</button>
            <button type="button" role="menuitem" onClick={() => beginSidebarRename(sidebarMenuConversation)}>重命名</button>
            <button type="button" role="menuitem" onClick={() => requestArchiveConversation(sidebarMenuConversation)}>归档</button>
            <span className="sidebar-menu-divider" role="separator" />
            <button type="button" role="menuitem" onClick={() => copyConversationId(sidebarMenuConversation)}>复制会话 ID</button>
            <button type="button" role="menuitem" onClick={() => copyConversationDeepLink(sidebarMenuConversation)}>复制深度链接</button>
            <span className="sidebar-menu-divider" role="separator" />
            <button type="button" role="menuitem" onClick={() => continueInNewConversation(sidebarMenuConversation)}>在新会话中继续</button>
          </div>
        )}
        {sidebarMenu && sidebarMenuProject && (
          <div ref={sidebarMenuRef} className="sidebar-context-menu sidebar-project-context-menu" data-sidebar-menu role="menu" aria-label={`“${sidebarMenuProject.title}”项目操作`} style={{ top: sidebarMenu.top }}>
            <button type="button" role="menuitem" onClick={() => togglePinnedProject(sidebarMenuProject)}><UiIcon name="pin" /><span>{pinnedProjectIds.includes(sidebarMenuProject.id) ? "取消置顶项目" : "置顶项目"}</span></button>
            <button type="button" role="menuitem" onClick={() => { setSidebarMenu(null); setProjectDialog({ mode: "edit", projectId: sidebarMenuProject.id }); }}><UiIcon name="edit" /><span>编辑项目</span></button>
            <button type="button" role="menuitem" disabled={!sidebarMenuProject.conversationIds.some((id) => !archivedConversationIds.includes(id))} onClick={() => requestArchiveProjectTasks(sidebarMenuProject)}><UiIcon name="archive" /><span>归档任务</span></button>
            <span className="sidebar-menu-divider" role="separator" />
            <button type="button" className="danger" role="menuitem" onClick={() => requestRemoveProject(sidebarMenuProject)}><UiIcon name="remove" /><span>移除</span></button>
          </div>
        )}
      </aside>
      <button className="workspace-sidebar-scrim" type="button" aria-label="关闭侧栏" onClick={() => setSidebarOpen(false)} />

      <section className="workspace-stage" aria-label="AI 对话工作台">
        <header className="workspace-topbar">
          <button className="mobile-sidebar-trigger" type="button" aria-label="打开侧栏" onClick={() => setSidebarOpen(true)}>☰</button>
          {renamingConversation && view === "chat" ? (
            <form className="workspace-title-form" onSubmit={(event) => { event.preventDefault(); const nextTitle = titleDraft.trim(); if (nextTitle) { setChatTitle(nextTitle); notify("会话标题已修改"); } setRenamingConversation(false); }}>
              <input value={titleDraft} maxLength={20} onChange={(event) => setTitleDraft(event.target.value)} aria-label="会话标题" autoFocus />
              <button type="submit">保存</button><button type="button" onClick={() => setRenamingConversation(false)}>取消</button>
            </form>
          ) : (
            <div className="workspace-title-block"><strong>{workspaceTitle}</strong><small>{workspaceSubtitle}</small></div>
          )}
          <div className="workspace-topbar-actions">
            {view === "chat" && (routeKind === "data" || routeKind === "failure") && <button type="button" className="topbar-scope-button" onClick={() => setScopePanelOpen(true)}>调整范围</button>}
            <button className="demo-button" type="button" onClick={() => setDemoOpen(true)}>{copy.demo} <span>10</span></button>
            <button className="topbar-new-button" type="button" aria-label="新建会话" title="新建会话" onClick={resetConversation}>＋</button>
            {view === "chat" && lastQuestion && (
              <div className="more-control">
                <button type="button" className="topbar-more-button" aria-label="会话操作" aria-expanded={conversationMenuOpen} onClick={() => setConversationMenuOpen((current) => !current)}>•••</button>
                {conversationMenuOpen && <div className="more-menu"><button type="button" onClick={() => { setTitleDraft(chatTitle); setRenamingConversation(true); setConversationMenuOpen(false); }}>修改标题</button><button type="button" className="danger" onClick={() => { setConversationMenuOpen(false); setConfirmState({ title: "删除当前会话？", description: "会话消息与当前附件将被删除，长期记忆不会自动删除。", confirmLabel: "删除会话", tone: "danger", action: () => { resetConversation(); notify("会话已删除"); } }); }}>删除会话</button></div>}
              </div>
            )}
          </div>
        </header>

        <main id="main-content" className="workspace-main">
        {view === "home" && (
          <HomeView
            question={homeQuestion}
            setQuestion={setHomeQuestion}
            composerRef={homeComposerRef}
            fileRef={homeFileRef}
            onKeyDown={(event) => handleComposerKeyDown(event, "home")}
            onSubmit={(event) => { event.preventDefault(); startProcessing(homeQuestion); }}
            onFiles={(event) => handleFiles(event, true)}
            onSuggestion={(suggestion) => chooseSuggestion(suggestion, "home")}
            onDaily={() => switchView("daily")}
            scope={scope}
            language={languagePreference}
            profile={executiveProfile}
            onOrganizationsChange={updateOrganizations}
          />
        )}
        {view === "chat" && (
          <ChatView
            question={lastQuestion}
            previousQuestion={previousQuestion}
            stage={chatStage}
            route={routeKind}
            answer={activeDataAnswer}
            answerVersion={answerVersion}
            scope={scope}
            files={files}
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            inheritedNotice={inheritedNotice}
            newTopicNotice={newTopicNotice}
            memoryCandidate={memoryCandidate}
            clarificationRound={clarificationRound}
            clarificationOrganizations={clarificationOrganizations}
            setClarificationOrganizations={setClarificationOrganizations}
            clarificationOwner={clarificationOwner}
            setClarificationOwner={setClarificationOwner}
            draft={chatDraft}
            setDraft={setChatDraft}
            fileRef={chatFileRef}
            onOpenScope={() => setScopePanelOpen(true)}
            onOrganizationsChange={updateOrganizations}
            onStop={stopCurrent}
            onRetry={retryCurrent}
            onConfirmClarification={confirmClarification}
            onFiles={(event) => handleFiles(event, false)}
            onDeleteFile={requestDeleteFile}
            onKeyDown={(event) => handleComposerKeyDown(event, "chat")}
            onSubmit={(event) => { event.preventDefault(); startProcessing(chatDraft); }}
            onSuggestion={(suggestion) => chooseSuggestion(suggestion, "chat")}
            onNotify={notify}
            onSaveMemory={saveMemoryCandidate}
            onDismissMemory={() => setMemoryCandidate(false)}
            language={languagePreference}
          />
        )}
        </main>
      </section>

      {activePanel && (
        <div className="workspace-panel-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setActivePanel(null); }}>
          <aside className={`workspace-detail-panel ${reportPanelOpen ? "report-detail-panel" : ""}`} role="dialog" aria-modal="true" aria-labelledby="workspace-panel-title">
            <header>
              <div><h2 id="workspace-panel-title">{panelTitle[activePanel]}</h2><small>工作台下钻</small></div>
              <div className="panel-header-actions">
                {reportPanelOpen && <button type="button" className="panel-feishu-button" onClick={() => setFeishuPreview((current) => !current)}>{feishuPreview ? "收起飞书消息样例" : "查看飞书消息样例"}</button>}
                <button type="button" className="panel-close-button" onClick={() => setActivePanel(null)} aria-label="关闭面板">×</button>
              </div>
            </header>
            <div className="workspace-detail-scroll">
              {activePanel === "history" && <HistoryView conversations={conversations} onOpen={openConversation} onNew={resetConversation} onRename={renameConversation} onDelete={requestDeleteConversation} />}
              {activePanel === "memory" && <MemoryView enabled={memoryEnabled} setEnabled={(enabled) => { setMemoryEnabled(enabled); notify(enabled ? "长期记忆已开启" : "长期记忆已关闭，现有内容仍保留"); }} memories={memories} onSave={saveMemory} onDelete={requestDeleteMemory} onClear={requestClearMemories} onOpenSource={() => switchView("history")} />}
              {activePanel === "daily" && <DailySummaryView feishuPreview={feishuPreview} onQuestion={(question) => startProcessing(question)} />}
              {activePanel === "weekly" && <WeeklyBriefView feishuPreview={feishuPreview} onQuestion={(question) => startProcessing(question)} />}
              {activePanel === "capabilities" && <CapabilitiesView language={languagePreference} onBack={() => setActivePanel(null)} />}
              {activePanel === "account" && <AccountView memoryEnabled={memoryEnabled} onMemory={() => switchView("memory")} onLogout={onLogout} />}
            </div>
          </aside>
        </div>
      )}

      {personalCenterView && (
        <PersonalCenterWindow
          view={personalCenterView}
          setView={setPersonalCenterView}
          onClose={() => setPersonalCenterView(null)}
          themePreference={themePreference}
          onThemePreferenceChange={onThemePreferenceChange}
          language={languagePreference}
          profile={executiveProfile}
          onProfileChange={setExecutiveProfile}
          scope={scope}
          memoryEnabled={memoryEnabled}
          setMemoryEnabled={(enabled) => { setMemoryEnabled(enabled); notify(enabled ? "长期记忆已开启" : "长期记忆已关闭，现有内容仍保留"); }}
          memories={memories}
          onSaveMemory={saveMemory}
          onDeleteMemory={requestDeleteMemory}
          onClearMemories={requestClearMemories}
          onOpenMemorySource={() => { setPersonalCenterView(null); switchView("history"); }}
          onNotify={notify}
        />
      )}

      {scopePanelOpen && (
        <ScopePanel
          scope={scope}
          language={languagePreference}
          onClose={() => setScopePanelOpen(false)}
          onSave={(nextScope) => { setScope(nextScope); setScopePanelOpen(false); notify("范围已更新，将用于后续问题"); }}
        />
      )}
      {demoOpen && <DemoDrawer onClose={() => setDemoOpen(false)} onRun={runDemoScenario} />}
      {projectDialog && (
        <ProjectDialog
          key={projectDialog.mode === "create" ? "create-project" : `edit-${projectDialog.projectId}`}
          state={projectDialog}
          project={projectDialog.mode === "edit" ? sidebarProjects.find((project) => project.id === projectDialog.projectId) ?? null : null}
          onClose={() => setProjectDialog(null)}
          onSave={(title, description) => saveProject(projectDialog, title, description)}
        />
      )}
      {confirmState && (
        <ConfirmDialog
          state={confirmState}
          onCancel={() => setConfirmState(null)}
          onConfirm={() => { const action = confirmState.action; setConfirmState(null); action(); }}
        />
      )}
      {toast && <Toast message={toast} />}
    </div>
  );
}
