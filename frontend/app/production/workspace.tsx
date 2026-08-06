"use client";

import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ApiError, humanizeApiError } from "./api-client";
import { loadProductionBootstrap, productionServices } from "./services";
import type {
  AuthorizedModel,
  AuthMe,
  Conversation,
  ConversationMessage,
  DataCapabilities,
  DailyBrief,
  Job,
  Memory,
  OrganizationUnit,
  OrganizationScope,
  ProductionBootstrap,
  Project,
  Report,
} from "./types";
import { UiIcon } from "./ui-icon";
import {
  type ConfirmState,
  type ConversationProjectDialogState,
  type DailyBriefLoadState,
  type MemoryCreateHandler,
  type MemoryUpdateHandler,
  type PreferencesView,
  type ProfilePreferences,
  type ProjectDialogState,
  type SidebarMenuState,
  type ThemePreference,
  type UiLanguage,
  type WorkspacePanel,
  ALL_ORGANIZATIONS_SCOPE,
  ALL_SCOPE_ID,
  copy,
  languageOptions,
} from "./workspace-types";
import {
  environmentLabel,
  localizedDate,
  makeInitials,
  organizationScopeKey,
  preferredDisplayName,
  professionalSourceLabel,
  resolvedDailyBriefScopeKey,
  scopeFromConversation,
  scopeLabel,
  sortByPinnedAndRecent,
} from "./workspace-utils";
import {
  ConfirmDialog,
  ConversationProjectDialog,
  ProjectDialog,
  Toast,
} from "./workspace-dialogs";
import {
  ProductionComposer,
  ProductionConversation,
  ProductionHome,
  SidebarConversationRow,
} from "./workspace-views";
import {
  PreferencesWindow,
  WorkspaceDetailPanel,
} from "./workspace-panels";
import {
  readStoredTheme,
  readStoredUnreadConversationIds,
  resolveInitialLanguage,
  resolveInitialModelId,
  resolveInitialProfilePreferences,
} from "./workspace-state";
import {
  buildArchiveConversationConfirm,
  buildArchiveProjectTasksConfirm,
  buildConversationProjectDialogState,
  buildDeleteMemoryConfirm,
  buildProjectDialogStateForCreate,
  buildProjectDialogStateForEdit,
  buildRemoveProjectConfirm,
  buildSidebarMenuState,
  findJobForMessage,
} from "./workspace-actions";

export function ProductionWorkspace({
  initialBootstrap,
  onSessionExpired,
  onReload,
}: {
  initialBootstrap: ProductionBootstrap;
  onSessionExpired: () => void;
  onReload: () => Promise<void>;
}) {
  const [bootstrap, setBootstrap] = useState(initialBootstrap);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState("");
  const [draft, setDraft] = useState("");
  const [selectedOrganizationScope, setSelectedOrganizationScope] = useState<OrganizationScope>(ALL_ORGANIZATIONS_SCOPE);
  const [dailyBriefState, setDailyBriefState] = useState<DailyBriefLoadState>(() => ({
    scopeKey: resolvedDailyBriefScopeKey(initialBootstrap.dailyBrief),
    status: initialBootstrap.dailyBrief ? "ready" : "error",
    data: initialBootstrap.dailyBrief,
  }));
  const [selectedModelId, setSelectedModelId] = useState(
    resolveInitialModelId(initialBootstrap),
  );
  const [sending, setSending] = useState(false);
  const [workspaceError, setWorkspaceError] = useState("");
  const [toast, setToast] = useState("");
  const [, setClockTick] = useState(0);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [languageMenuOpen, setLanguageMenuOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activePanel, setActivePanel] = useState<WorkspacePanel | null>(null);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [preferencesView, setPreferencesView] = useState<PreferencesView | null>(null);
  const [sidebarMenu, setSidebarMenu] = useState<SidebarMenuState | null>(null);
  const [projectDialog, setProjectDialog] = useState<ProjectDialogState | null>(null);
  const [conversationProjectDialog, setConversationProjectDialog] = useState<ConversationProjectDialogState | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [renameConversationId, setRenameConversationId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [unreadConversationIds, setUnreadConversationIds] = useState<string[]>(readStoredUnreadConversationIds);
  const [expandedProjectIds, setExpandedProjectIds] = useState<string[]>([]);
  const [projectConversations, setProjectConversations] = useState<Record<string, Conversation[]>>({});
  const [projectLoadingId, setProjectLoadingId] = useState<string | null>(null);
  const [themePreference, setThemePreference] = useState<ThemePreference>(readStoredTheme);
  const [languagePreference, setLanguagePreference] = useState<UiLanguage>(() => resolveInitialLanguage(initialBootstrap));
  const [profilePreferences, setProfilePreferences] = useState<ProfilePreferences>(() => resolveInitialProfilePreferences(initialBootstrap));
  const [memoryEnabled, setMemoryEnabled] = useState(initialBootstrap.personalProfile?.memory_enabled ?? initialBootstrap.me.user.memory_enabled);
  const accountRef = useRef<HTMLDivElement>(null);
  const sidebarMenuRef = useRef<HTMLDivElement>(null);
  const deepLinkHandled = useRef(false);

  const me = bootstrap.me;
  const c = copy[languagePreference];
  const organizationUnits = bootstrap.organizationUnits;
  const businessDataReady = organizationUnits.length > 0;
  const dataCapabilities = bootstrap.dataCapabilities;
  const dailyBriefScopeRequestKey = organizationScopeKey(selectedOrganizationScope);
  const dailyBrief = dailyBriefState.scopeKey === dailyBriefScopeRequestKey && dailyBriefState.status === "ready"
    ? dailyBriefState.data
    : null;
  const dailyBriefStatus: DailyBriefLoadState["status"] = dailyBriefState.scopeKey === dailyBriefScopeRequestKey
    ? dailyBriefState.status
    : "loading";
  const activeConversation = bootstrap.conversations.find((item) => item.id === activeConversationId) ?? null;
  const selectedScopeLabel = scopeLabel(selectedOrganizationScope, organizationUnits, languagePreference);
  const sortedProjects = useMemo(() => sortByPinnedAndRecent(bootstrap.projects), [bootstrap.projects]);
  const pinnedConversations = useMemo(
    () => sortByPinnedAndRecent(bootstrap.conversations.filter((item) => item.pinned_at && !item.archived_at)),
    [bootstrap.conversations],
  );
  const recentConversations = useMemo(
    () => [...bootstrap.conversations]
      .filter((item) => !item.project_id && !item.pinned_at && !item.archived_at)
      .sort((first, second) => (second.last_message_at || second.updated_at).localeCompare(first.last_message_at || first.updated_at))
      .slice(0, 14),
    [bootstrap.conversations],
  );
  const latestDailyReport = useMemo(
    () => bootstrap.reports
      .filter((report) => report.kind === "daily" && (report.status === "published" || report.status === "completed"))
      .sort((first, second) => String(second.published_at || second.created_at).localeCompare(String(first.published_at || first.created_at)))[0] ?? null,
    [bootstrap.reports],
  );
  const optionalWarning = Object.values(bootstrap.optionalErrors)[0];
  const userInitials = makeInitials(preferredDisplayName(me)).toUpperCase();
  // Production mode never falls back to bundled demo fixtures: every render reads
  // real backend data, and any error surfaces as a 脱敏演示环境 banner instead of demo data.
  useEffect(() => {
    if (dailyBriefState.scopeKey === dailyBriefScopeRequestKey) return;
    let cancelled = false;
    const requestedScopeKey = dailyBriefScopeRequestKey;
    const organizationUnitIds = requestedScopeKey === "all_authorized" ? [] : requestedScopeKey.split(",").filter(Boolean);
    void productionServices.data.dailyBrief(organizationUnitIds).then((nextBrief) => {
      if (cancelled) return;
      setBootstrap((current) => ({ ...current, dailyBrief: nextBrief }));
      setDailyBriefState({ scopeKey: requestedScopeKey, status: "ready", data: nextBrief });
    }).catch(() => {
      if (cancelled) return;
      setDailyBriefState({ scopeKey: requestedScopeKey, status: "error", data: null });
    });
    return () => { cancelled = true; };
  }, [dailyBriefScopeRequestKey, dailyBriefState.scopeKey]);

  useEffect(() => {
    if (!activeConversationId) return;
    // 不再使用 EventSource 轮询；消息通过 sendMessageStream 的 SSE 流实时获取。
    // 这里仅做一次初始消息加载（如果有需要）。
    return () => {};
  }, [activeConversationId]);

  useEffect(() => {
    document.documentElement.dataset.theme = themePreference;
    document.documentElement.style.colorScheme = themePreference === "system" ? "light dark" : themePreference;
    window.localStorage.setItem("executive-workbench-theme", themePreference);
  }, [themePreference]);

  useEffect(() => {
    document.documentElement.lang = languagePreference;
    window.localStorage.setItem("executive-workbench-language", languagePreference);
  }, [languagePreference]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const timer = window.setInterval(() => setClockTick((value) => value + 1), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!sidebarOpen) return;
    const closeSidebar = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", closeSidebar);
    return () => window.removeEventListener("keydown", closeSidebar);
  }, [sidebarOpen]);

  useEffect(() => {
    window.localStorage.setItem("executive-workbench-unread-conversations", JSON.stringify(unreadConversationIds));
  }, [unreadConversationIds]);

  const runRequest = useCallback(async <T,>(action: () => Promise<T>): Promise<T | undefined> => {
    try {
      setWorkspaceError("");
      return await action();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onSessionExpired();
        return undefined;
      }
      setWorkspaceError(humanizeApiError(error));
      return undefined;
    }
  }, [onSessionExpired]);

  const refreshWorkspace = useCallback(async () => {
    const refreshed = await runRequest(() => loadProductionBootstrap());
    if (refreshed) setBootstrap(refreshed);
  }, [runRequest]);

  const openConversation = useCallback(async (conversation: Conversation) => {
    setActiveConversationId(conversation.id);
    setActiveProjectId(null);
    setMessages([]);
    setMessagesError("");
    setMessagesLoading(true);
    setSidebarOpen(false);
    setActivePanel(null);
    setUnreadConversationIds((current) => current.filter((id) => id !== conversation.id));
    setSelectedOrganizationScope(scopeFromConversation(conversation));
    setSelectedModelId(
      conversation.selected_model_id
        ?? bootstrap.authorizedModels.find((model) => model.is_default)?.model_id
        ?? bootstrap.authorizedModels[0]?.model_id
        ?? "",
    );
    try {
      const result = await productionServices.conversations.messages(conversation.id);
      setMessages(result.items);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onSessionExpired();
        return;
      }
      setMessagesError(humanizeApiError(error));
    } finally {
      setMessagesLoading(false);
    }
  }, [bootstrap.authorizedModels, onSessionExpired]);

  useEffect(() => {
    if (deepLinkHandled.current) return;
    deepLinkHandled.current = true;
    const conversationId = new URLSearchParams(window.location.search).get("conversation");
    if (!conversationId) return;
    const conversation = initialBootstrap.conversations.find((item) => item.id === conversationId);
    if (!conversation) return;
    const timer = window.setTimeout(() => void openConversation(conversation), 0);
    return () => window.clearTimeout(timer);
  }, [initialBootstrap.conversations, openConversation]);

  function newConversation(projectId: string | null = null) {
    setActiveConversationId(null);
    setActiveProjectId(projectId);
    setMessages([]);
    setMessagesError("");
    setDraft("");
    setSidebarOpen(false);
    setActivePanel(null);
    const project = bootstrap.projects.find((item) => item.id === projectId);
    setSelectedOrganizationScope(project?.organization_unit_id
      ? { mode: "selected", organization_unit_ids: [project.organization_unit_id] }
      : ALL_ORGANIZATIONS_SCOPE);
    setSelectedModelId(
      bootstrap.authorizedModels.find((model) => model.is_default)?.model_id
        ?? bootstrap.authorizedModels[0]?.model_id
        ?? "",
    );
    window.history.replaceState(null, "", window.location.pathname);
  }

  const newConversationRef = useRef(newConversation);
  newConversationRef.current = newConversation;

  useEffect(() => {
    const closeFloating = (event: PointerEvent) => {
      const target = event.target as HTMLElement;
      if (!accountRef.current?.contains(target)) {
        setAccountMenuOpen(false);
        setLanguageMenuOpen(false);
      }
      if (!target.closest("[data-sidebar-menu]")) setSidebarMenu(null);
    };
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        newConversationRef.current();
      }
      if (event.key === "Escape") {
        setAccountMenuOpen(false);
        setLanguageMenuOpen(false);
        setSidebarMenu(null);
      }
    };
    window.addEventListener("pointerdown", closeFloating);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", closeFloating);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || sending) return;
    if (!selectedModelId || !bootstrap.authorizedModels.some((model) => model.model_id === selectedModelId)) {
      setWorkspaceError(selectedModelId
        ? "本会话原模型已取消授权，请先重新选择可用模型。"
        : "管理员尚未授权可用模型，暂时无法发送消息。");
      return;
    }
    setSending(true);
    await runRequest(async () => {
      let conversationId = activeConversationId;
      const isNewConversation = !conversationId;
      if (isNewConversation) {
        const createdConversation = await productionServices.conversations.create({
          title: content.slice(0, 42),
          organization_scope: selectedOrganizationScope,
          project_id: activeProjectId ?? undefined,
          model_id: selectedModelId,
        });
        conversationId = createdConversation.id;
        setActiveConversationId(conversationId);
        setBootstrap((current) => ({
          ...current,
          conversations: [createdConversation, ...current.conversations],
        }));
        if (activeProjectId) {
          setProjectConversations((current) => ({
            ...current,
            [activeProjectId]: [createdConversation, ...(current[activeProjectId] ?? [])],
          }));
        }
      }
      // 创建 user message 占位（乐观更新）
      const tempUserMsg: ConversationMessage = {
        id: `temp-user-${Date.now()}`,
        conversation_id: conversationId,
        role: "user",
        content,
        sequence: messages.length + 1,
        status: "completed",
        created_at: new Date().toISOString(),
        evidence: [],
        jobs: [],
      } as unknown as ConversationMessage;
      setMessages((current) => [...current, tempUserMsg]);

      // 创建 assistant 占位（流式填充）
      const tempAssistantId = `temp-assistant-${Date.now()}`;
      const tempAssistantMsg: ConversationMessage = {
        id: tempAssistantId,
        conversation_id: conversationId,
        role: "assistant",
        content: "",
        sequence: messages.length + 2,
        status: "running",
        created_at: new Date().toISOString(),
        evidence: [],
        jobs: [],
      } as unknown as ConversationMessage;
      setMessages((current) => [...current, tempAssistantMsg]);

      setDraft("");

      // 流式接收响应
      let fullContent = "";
      try {
        for await (const event of productionServices.conversations.sendMessageStream(
          conversationId,
          content,
          selectedOrganizationScope,
          selectedModelId,
        )) {
          if (event.type === "delta" && event.content) {
            fullContent += event.content;
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === tempAssistantId);
              if (idx < 0) return current;
              const next = [...current];
              next[idx] = { ...next[idx], content: fullContent };
              return next;
            });
          } else if (event.type === "done") {
            // 用真实 message 替换占位
            const realContent = event.content ?? fullContent;
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === tempAssistantId);
              if (idx < 0) return current;
              const next = [...current];
              next[idx] = {
                ...next[idx],
                id: event.message_id ?? tempAssistantId,
                content: realContent,
                status: "completed",
              };
              return next;
            });
            // 同时更新 user message 占位为真实 ID（如果有）
            fullContent = realContent;
          } else if (event.type === "error") {
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === tempAssistantId);
              if (idx < 0) return current;
              const next = [...current];
              next[idx] = {
                ...next[idx],
                content: event.error ? `回答失败：${event.error}` : "回答失败，请重试。",
                status: "failed",
              };
              return next;
            });
          }
        }
      } catch (err) {
        setMessages((current) => {
          const idx = current.findIndex((m) => m.id === tempAssistantId);
          if (idx < 0) return current;
          const next = [...current];
          next[idx] = {
            ...next[idx],
            content: "网络异常，请重试。",
            status: "failed",
          };
          return next;
        });
      }

      window.history.replaceState(null, "", `${window.location.pathname}?conversation=${encodeURIComponent(conversationId)}`);
      // 仅在新会话创建时刷新一次（更新 sidebar 的会话列表/时间戳），
      // 已有会话的 SSE 流已实时更新消息，无需重载整个 bootstrap。
      if (isNewConversation) {
        await refreshWorkspace();
      }
    });
    setSending(false);
  }

  async function changeSelectedModel(modelId: string) {
    if (modelId === selectedModelId) return;
    const previous = selectedModelId;
    setSelectedModelId(modelId);
    if (!activeConversationId) return;
    const updated = await runRequest(
      () => productionServices.conversations.update(activeConversationId, { model_id: modelId }),
    );
    if (!updated) {
      setSelectedModelId(previous);
      return;
    }
    setBootstrap((current) => ({
      ...current,
      conversations: current.conversations.map((item) => item.id === updated.id ? updated : item),
    }));
    setToast(`本会话后续将使用${bootstrap.authorizedModels.find((item) => item.model_id === modelId)?.display_name ?? modelId}`);
  }

  async function moveConversationToProject(conversationId: string, projectId: string | null) {
    const updated = await runRequest(
      () => productionServices.conversations.setProject(conversationId, projectId),
    );
    if (!updated) return false;
    setBootstrap((current) => ({
      ...current,
      conversations: current.conversations.map((item) => item.id === updated.id ? updated : item),
    }));
    setProjectConversations((current) => {
      const next = Object.fromEntries(
        Object.entries(current).map(([id, items]) => [
          id,
          items.filter((item) => item.id !== conversationId),
        ]),
      );
      if (projectId) next[projectId] = [updated, ...(next[projectId] ?? [])];
      return next;
    });
    setConversationProjectDialog(null);
    setSidebarMenu(null);
    setToast(projectId ? "会话已移入项目" : "会话已移出项目");
    return true;
  }

  async function cancelAnswer(messageId: string) {
    const job = findJobForMessage(bootstrap.jobs, messageId);
    if (!job) return;
    const updated = await runRequest(() => productionServices.jobs.cancel(job.id));
    if (!updated) return;
    setBootstrap((current) => ({
      ...current,
      jobs: current.jobs.map((item) => (item.id === updated.id ? updated : item)),
    }));
    setMessages((current) => current.map((message) => (
      message.id === messageId
        ? { ...message, status: "failed", content: "请求已取消" }
        : message
    )));
    setToast("已停止本次处理");
  }

  async function retryAnswer(messageId: string) {
    const job = findJobForMessage(bootstrap.jobs, messageId);
    if (!job || !activeConversationId) return;
    const retried = await runRequest(() => productionServices.jobs.retry(job.id));
    if (!retried) return;
    setBootstrap((current) => ({ ...current, jobs: [retried, ...current.jobs] }));
    const refreshed = await runRequest(
      () => productionServices.conversations.messages(activeConversationId),
    );
    if (refreshed) setMessages(refreshed.items);
    setToast("已重新进入受控处理流程");
  }

  async function changeMemoryEnabled(value: boolean) {
    const previous = memoryEnabled;
    setMemoryEnabled(value);
    const updated = await runRequest(() => productionServices.auth.updatePersonalProfile({
      salutation: profilePreferences.salutation,
      amount_unit: profilePreferences.amountUnit,
      response_style: profilePreferences.responseStyle,
      locale: languagePreference === "en" ? "en-US" : languagePreference,
      memory_enabled: value,
    }));
    if (!updated) {
      setMemoryEnabled(previous);
      return;
    }
    setBootstrap((current) => ({
      ...current,
      personalProfile: updated,
      me: { ...current.me, user: { ...current.me.user, memory_enabled: updated.memory_enabled } },
    }));
    setToast(value ? "长期记忆已开启" : "长期记忆已关闭");
  }

  async function saveProfilePreferences(value: ProfilePreferences) {
    const updated = await runRequest(() => productionServices.auth.updatePersonalProfile({
      salutation: value.salutation,
      amount_unit: value.amountUnit,
      response_style: value.responseStyle,
      locale: languagePreference === "en" ? "en-US" : languagePreference,
      memory_enabled: memoryEnabled,
    }));
    if (!updated) return false;
    setProfilePreferences({
      salutation: updated.salutation,
      amountUnit: updated.amount_unit,
      responseStyle: updated.response_style,
    });
    setBootstrap((current) => ({
      ...current,
      personalProfile: updated,
      me: {
        ...current.me,
        user: {
          ...current.me.user,
          locale: updated.locale,
          memory_enabled: updated.memory_enabled,
        },
      },
    }));
    setToast("服务偏好已安全保存");
    return true;
  }

  async function changeLanguage(value: UiLanguage) {
    const previous = languagePreference;
    setLanguagePreference(value);
    const updated = await runRequest(() => productionServices.auth.updatePersonalProfile({
      salutation: profilePreferences.salutation,
      amount_unit: profilePreferences.amountUnit,
      response_style: profilePreferences.responseStyle,
      locale: value === "en" ? "en-US" : value,
      memory_enabled: memoryEnabled,
    }));
    if (!updated) {
      setLanguagePreference(previous);
      return;
    }
    setBootstrap((current) => ({ ...current, personalProfile: updated }));
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  async function logout() {
    await runRequest(async () => {
      await productionServices.auth.logout();
      onSessionExpired();
    });
  }

  async function openReport(kind: "daily" | "weekly", reportId?: string) {
    setActivePanel(kind);
    setSelectedReport(null);
    setReportLoading(false);
    const summary = reportId
      ? bootstrap.reports.find((item) => item.id === reportId)
      : bootstrap.reports
        .filter((item) => item.kind === kind)
        .sort((first, second) => second.period_end.localeCompare(first.period_end))[0];
    if (!summary) return;
    setReportLoading(true);
    const detail = await runRequest(() => productionServices.reports.get(summary.id));
    if (detail) setSelectedReport(detail);
    setReportLoading(false);
  }

  async function toggleConversationPinned(conversation: Conversation) {
    const updated = await runRequest(() => productionServices.conversations.setPinned(conversation.id, !conversation.pinned_at));
    if (!updated) return;
    setBootstrap((current) => ({
      ...current,
      conversations: current.conversations.map((item) => item.id === updated.id ? updated : item),
    }));
    setSidebarMenu(null);
    setToast(updated.pinned_at ? "会话已置顶" : "已取消置顶");
  }

  async function renameConversation(conversationId: string, title: string) {
    const normalized = title.trim();
    if (!normalized) return;
    const updated = await runRequest(() => productionServices.conversations.update(conversationId, { title: normalized }));
    if (!updated) return;
    setBootstrap((current) => ({
      ...current,
      conversations: current.conversations.map((item) => item.id === updated.id ? updated : item),
    }));
    setProjectConversations((current) => Object.fromEntries(
      Object.entries(current).map(([projectId, items]) => [
        projectId,
        items.map((item) => item.id === updated.id ? updated : item),
      ]),
    ));
    setRenameConversationId(null);
    setToast("会话名称已更新");
  }

  function requestArchiveConversation(conversation: Conversation) {
    setSidebarMenu(null);
    setConfirmState(buildArchiveConversationConfirm(conversation, async () => {
      const archived = await runRequest(async () => {
        await productionServices.conversations.archive(conversation.id);
        return true;
      });
      if (!archived) return;
      setBootstrap((current) => ({
        ...current,
        conversations: current.conversations.filter((item) => item.id !== conversation.id),
      }));
      setProjectConversations((current) => Object.fromEntries(
        Object.entries(current).map(([projectId, items]) => [projectId, items.filter((item) => item.id !== conversation.id)]),
      ));
      if (activeConversationId === conversation.id) newConversation();
      setToast("会话已归档");
    }));
  }

  function toggleUnread(conversationId: string) {
    setUnreadConversationIds((current) => current.includes(conversationId)
      ? current.filter((id) => id !== conversationId)
      : [...current, conversationId]);
    setSidebarMenu(null);
  }

  async function copyText(value: string, confirmation: string) {
    await navigator.clipboard.writeText(value);
    setSidebarMenu(null);
    setToast(confirmation);
  }

  async function toggleProject(projectId: string) {
    if (expandedProjectIds.includes(projectId)) {
      setExpandedProjectIds((current) => current.filter((id) => id !== projectId));
      return;
    }
    setExpandedProjectIds((current) => [...current, projectId]);
    if (projectConversations[projectId]) return;
    setProjectLoadingId(projectId);
    const result = await runRequest(() => productionServices.conversations.list(undefined, { projectId }));
    if (result) setProjectConversations((current) => ({ ...current, [projectId]: result.items }));
    setProjectLoadingId(null);
  }

  async function saveProject(state: ProjectDialogState, name: string, description: string, organizationUnitId: string) {
    const normalizedOrganization = organizationUnitId === ALL_SCOPE_ID ? undefined : organizationUnitId;
    const result = state.mode === "create"
      ? await runRequest(() => productionServices.projects.create(name, description || undefined, normalizedOrganization))
      : await runRequest(() => productionServices.projects.update(state.projectId, {
        name,
        description: description || null,
        organization_unit_id: normalizedOrganization || null,
      }));
    if (!result) return false;
    setBootstrap((current) => ({
      ...current,
      projects: state.mode === "create"
        ? [result, ...current.projects]
        : current.projects.map((item) => item.id === result.id ? result : item),
    }));
    setProjectDialog(null);
    if (state.mode === "create") setExpandedProjectIds((current) => [...current, result.id]);
    setToast(state.mode === "create" ? "项目已创建" : "项目已更新");
    return true;
  }

  async function toggleProjectPinned(project: Project) {
    const updated = await runRequest(() => productionServices.projects.setPinned(project.id, !project.pinned_at));
    if (!updated) return;
    setBootstrap((current) => ({
      ...current,
      projects: current.projects.map((item) => item.id === updated.id ? updated : item),
    }));
    setSidebarMenu(null);
    setToast(updated.pinned_at ? "项目已置顶" : "已取消项目置顶");
  }

  function requestArchiveProjectTasks(project: Project) {
    setSidebarMenu(null);
    setConfirmState(buildArchiveProjectTasksConfirm(project, async () => {
      let items = projectConversations[project.id];
      if (!items) {
        const result = await runRequest(() => productionServices.conversations.list(undefined, { projectId: project.id }));
        items = result?.items ?? [];
      }
      const archived = await runRequest(async () => {
        await Promise.all(items.map((item) => productionServices.conversations.archive(item.id)));
        return true;
      });
      if (!archived) return;
      const ids = new Set(items.map((item) => item.id));
      setBootstrap((current) => ({
        ...current,
        conversations: current.conversations.filter((item) => !ids.has(item.id)),
      }));
      setProjectConversations((current) => ({ ...current, [project.id]: [] }));
      if (activeConversationId && ids.has(activeConversationId)) newConversation();
      setToast("项目会话已归档");
    }));
  }

  function requestRemoveProject(project: Project) {
    setSidebarMenu(null);
    setConfirmState(buildRemoveProjectConfirm(project, async () => {
      const removed = await runRequest(async () => {
        await productionServices.projects.archive(project.id);
        return true;
      });
      if (!removed) return;
      setBootstrap((current) => ({
        ...current,
        projects: current.projects.filter((item) => item.id !== project.id),
        conversations: current.conversations.map((item) => (
          item.project_id === project.id ? { ...item, project_id: null } : item
        )),
      }));
      setProjectConversations((current) => {
        const next = { ...current };
        delete next[project.id];
        return next;
      });
      setExpandedProjectIds((current) => current.filter((id) => id !== project.id));
      setActiveProjectId((current) => current === project.id ? null : current);
      setToast("项目已移除");
    }));
  }

  function openSidebarMenu(
    event: React.MouseEvent<HTMLButtonElement>,
    state: { kind: "conversation"; conversationId: string } | { kind: "project"; projectId: string },
  ) {
    event.stopPropagation();
    setSidebarMenu(buildSidebarMenuState(event, state));
  }

  const sidebarMenuConversation = sidebarMenu?.kind === "conversation"
    ? bootstrap.conversations.find((item) => item.id === sidebarMenu.conversationId) ?? null
    : null;
  const sidebarMenuProject = sidebarMenu?.kind === "project"
    ? bootstrap.projects.find((item) => item.id === sidebarMenu.projectId) ?? null
    : null;

  const handleCreateMemory: MemoryCreateHandler = async (title, content, kind, organizationUnitId) => {
    const created = await runRequest(() => productionServices.memories.create({ title, content, kind, organization_unit_id: organizationUnitId || undefined }));
    if (created) { setBootstrap((current) => ({ ...current, memories: [created, ...current.memories] })); setToast("记忆已保存"); return true; }
    return false;
  };

  const handleUpdateMemory: MemoryUpdateHandler = async (memory, values) => {
    const updated = await runRequest(() => productionServices.memories.update(memory.id, values));
    if (updated) { setBootstrap((current) => ({ ...current, memories: current.memories.map((item) => item.id === updated.id ? updated : item) })); setToast("记忆已更新"); return true; }
    return false;
  };

  const handleDeleteMemory = (memory: Memory) => setConfirmState(buildDeleteMemoryConfirm(memory, async () => {
    const removed = await runRequest(async () => {
      await productionServices.memories.remove(memory.id);
      return true;
    });
    if (removed) {
      setBootstrap((current) => ({ ...current, memories: current.memories.filter((item) => item.id !== memory.id) }));
      setToast("记忆已删除");
    }
  }));

  return (
    <div className={`product-shell workbench-shell production-workbench production-workbench-v2 ${sidebarOpen ? "sidebar-open" : ""} ${sidebarCollapsed ? "sidebar-collapsed" : ""}`} data-app-mode={me.app_mode} data-app-environment={me.app_env}>
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      {(workspaceError || optionalWarning) && <div className="network-banner" role="status"><span>{workspaceError || `部分辅助能力暂不可用：${optionalWarning}`}</span><button type="button" onClick={() => setWorkspaceError("")} aria-label="关闭提示">×</button></div>}

      <aside className="workspace-sidebar" aria-label="工作台侧栏">
        <header className="sidebar-brand-row">
          <button className="sidebar-brand" type="button" onClick={() => newConversation()}>
            <span className="brand-glyph" aria-hidden="true">董</span>
            <span className="sidebar-label"><strong>{c.brand}</strong><small>{me.enterprise.name}</small></span>
          </button>
          <button className="sidebar-collapse" type="button" aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"} onClick={() => setSidebarCollapsed((current) => !current)}>{sidebarCollapsed ? "›" : "‹"}</button>
        </header>

        <div className="sidebar-scroll-region">
          <button className="new-conversation-button" type="button" onClick={() => newConversation()}><span aria-hidden="true">＋</span><strong className="sidebar-label">{c.newConversation}</strong><kbd className="sidebar-label">⌘ K</kbd></button>
          <nav className="workspace-navigation" aria-label="经营工作台功能">
            <button type="button" className={activePanel === "daily" ? "active" : ""} onClick={() => void openReport("daily")}><span aria-hidden="true">今</span><strong className="sidebar-label">{c.daily}</strong></button>
            <button type="button" className={activePanel === "weekly" ? "active" : ""} onClick={() => void openReport("weekly")}><span aria-hidden="true">周</span><strong className="sidebar-label">{c.weekly}</strong></button>
            <button type="button" className={activePanel === "history" ? "active" : ""} onClick={() => setActivePanel("history")}><span aria-hidden="true">历</span><strong className="sidebar-label">{c.history}</strong></button>
            <button type="button" className={activePanel === "memory" ? "active" : ""} onClick={() => setActivePanel("memory")}><span aria-hidden="true">记</span><strong className="sidebar-label">{c.memory}</strong></button>
          </nav>

          <div className="sidebar-sections">
            {pinnedConversations.length > 0 && (
              <section className="sidebar-section" aria-labelledby="production-pinned-title">
                <header className="sidebar-section-header"><span id="production-pinned-title">{c.pinned}</span></header>
                <div className="sidebar-list">
                  {pinnedConversations.map((conversation) => (
                    <SidebarConversationRow
                      key={conversation.id}
                      conversation={conversation}
                      active={activeConversationId === conversation.id}
                      unread={unreadConversationIds.includes(conversation.id)}
                      renaming={renameConversationId === conversation.id}
                      renameDraft={renameDraft}
                      setRenameDraft={setRenameDraft}
                      onRename={() => void renameConversation(conversation.id, renameDraft)}
                      onCancelRename={() => setRenameConversationId(null)}
                      onOpen={() => void openConversation(conversation)}
                      onMenu={(event) => openSidebarMenu(event, { kind: "conversation", conversationId: conversation.id })}
                    />
                  ))}
                </div>
              </section>
            )}

            <section className="sidebar-section" aria-labelledby="production-projects-title">
              <header className="sidebar-section-header"><span id="production-projects-title">{c.projects}</span><button className="sidebar-add-project" type="button" aria-label="新建项目" onClick={() => setProjectDialog(buildProjectDialogStateForCreate())}>＋</button></header>
              <div className="sidebar-list">
                {sortedProjects.length ? sortedProjects.map((project) => {
                  const expanded = expandedProjectIds.includes(project.id);
                  const items = projectConversations[project.id] ?? [];
                  return (
                    <div className={`sidebar-project ${project.pinned_at ? "pinned" : ""}`} key={project.id}>
                      <div className="sidebar-project-row-shell">
                        <button className="sidebar-project-button" type="button" aria-expanded={expanded} title={project.description || project.name} onClick={() => void toggleProject(project.id)}>
                          <span className="sidebar-disclosure" aria-hidden="true">{expanded ? "⌄" : "›"}</span><span className="sidebar-project-mark" aria-hidden="true" /><strong>{project.name}</strong>
                        </button>
                        <button type="button" className="sidebar-row-menu-button sidebar-project-menu-button" data-sidebar-menu aria-label={`打开“${project.name}”项目菜单`} onClick={(event) => openSidebarMenu(event, { kind: "project", projectId: project.id })}>•••</button>
                      </div>
                      {expanded && <div className="sidebar-project-conversations">
                        {projectLoadingId === project.id && <small className="sidebar-project-loading">正在读取项目会话…</small>}
                        {projectLoadingId !== project.id && items.map((conversation) => <button type="button" key={conversation.id} className={activeConversationId === conversation.id ? "active" : ""} onClick={() => void openConversation(conversation)}><span aria-hidden="true" /><strong>{conversation.title}</strong></button>)}
                        <button type="button" className={`sidebar-project-start-button ${activeProjectId === project.id && !activeConversationId ? "active" : ""}`} onClick={() => newConversation(project.id)}><span aria-hidden="true">＋</span><strong>在此项目新建会话</strong></button>
                      </div>}
                    </div>
                  );
                }) : <small className="sidebar-label sidebar-empty-copy">{c.noProject}</small>}
              </div>
            </section>

            <section className="sidebar-section" aria-labelledby="production-recent-title">
              <header className="sidebar-section-header"><span id="production-recent-title">{c.recent}</span><button type="button" onClick={() => setActivePanel("history")}>{c.all}</button></header>
              <div className="sidebar-list">
                {recentConversations.length ? recentConversations.map((conversation) => (
                  <SidebarConversationRow
                    key={conversation.id}
                    conversation={conversation}
                    active={activeConversationId === conversation.id}
                    unread={unreadConversationIds.includes(conversation.id)}
                    renaming={renameConversationId === conversation.id}
                    renameDraft={renameDraft}
                    setRenameDraft={setRenameDraft}
                    onRename={() => void renameConversation(conversation.id, renameDraft)}
                    onCancelRename={() => setRenameConversationId(null)}
                    onOpen={() => void openConversation(conversation)}
                    onMenu={(event) => openSidebarMenu(event, { kind: "conversation", conversationId: conversation.id })}
                  />
                )) : <small className="sidebar-label sidebar-empty-copy">{c.noConversation}</small>}
              </div>
            </section>
          </div>
        </div>

        <footer className="sidebar-footer">
          <button type="button" className="sidebar-data-status" onClick={() => setActivePanel("scope")}><span className="status-dot positive" aria-hidden="true" /><span className="sidebar-label"><strong>{businessDataReady ? "经营数据已接入" : c.dataMissing}</strong><small>{dataCapabilities ? `${professionalSourceLabel(dataCapabilities.source_label)} · ${organizationUnits.length} 个事业部` : businessDataReady ? "等待首次数据同步" : "请联系企业管理员"}</small></span></button>
          <div ref={accountRef} className="profile-control workspace-profile">
            <button className="profile-button" type="button" aria-label="打开个人菜单" aria-expanded={accountMenuOpen} onClick={() => { setAccountMenuOpen((current) => !current); setLanguageMenuOpen(false); }}><span className="profile-avatar" aria-hidden="true">{userInitials}</span><span className="sidebar-label"><strong>{preferredDisplayName(me)}</strong><small>{selectedScopeLabel}</small></span><span className="profile-menu-chevron sidebar-label" aria-hidden="true">{accountMenuOpen ? "⌄" : "›"}</span></button>
            {accountMenuOpen && <div className="profile-menu account-menu" role="menu" aria-label="个人菜单">
              <button type="button" className="account-menu-identity" role="menuitem" onClick={() => { setPreferencesView("profile"); setAccountMenuOpen(false); }}><span className="account-menu-avatar" aria-hidden="true">{userInitials}</span><span><strong>{preferredDisplayName(me)}</strong><small>{me.user.email}</small></span><UiIcon name="chevron" /></button>
              <div className="profile-menu-divider" />
              <button type="button" className="account-menu-item" role="menuitem" onClick={() => { setPreferencesView("appearance"); setAccountMenuOpen(false); }}><UiIcon name="settings" /><span>{c.settings}</span></button>
              <div className="account-language-control">
                <button type="button" className="account-menu-item" role="menuitem" aria-haspopup="menu" aria-expanded={languageMenuOpen} onClick={() => setLanguageMenuOpen((current) => !current)}><UiIcon name="language" /><span>{c.language}</span><small>{languageOptions.find((option) => option.id === languagePreference)?.label}</small><UiIcon name="chevron" /></button>
                {languageMenuOpen && <div className="language-submenu" role="menu" aria-label="选择界面语言">{languageOptions.map((option) => <button type="button" key={option.id} className={languagePreference === option.id ? "selected" : ""} role="menuitemradio" aria-checked={languagePreference === option.id} onClick={() => { void changeLanguage(option.id); setLanguageMenuOpen(false); setAccountMenuOpen(false); }}><span>{option.label}</span><span aria-hidden="true">{languagePreference === option.id ? "✓" : ""}</span></button>)}</div>}
              </div>
              <div className="profile-menu-divider" />
              <button type="button" className="account-menu-item account-menu-logout" role="menuitem" onClick={() => void logout()}><UiIcon name="logout" /><span>{c.logout}</span></button>
            </div>}
          </div>
        </footer>

        {sidebarMenuConversation && <div ref={sidebarMenuRef} className="sidebar-context-menu" data-sidebar-menu role="menu" style={{ top: sidebarMenu?.top }}>
          <button type="button" role="menuitem" onClick={() => void toggleConversationPinned(sidebarMenuConversation)}>{sidebarMenuConversation.pinned_at ? "取消置顶" : "置顶"}</button>
          <button type="button" role="menuitem" onClick={() => toggleUnread(sidebarMenuConversation.id)}>{unreadConversationIds.includes(sidebarMenuConversation.id) ? "标记为已读" : "标记未读"}</button>
          <button type="button" role="menuitem" onClick={() => { setRenameConversationId(sidebarMenuConversation.id); setRenameDraft(sidebarMenuConversation.title); setSidebarMenu(null); }}>重命名</button>
          <button type="button" role="menuitem" onClick={() => { setConversationProjectDialog(buildConversationProjectDialogState(sidebarMenuConversation.id)); setSidebarMenu(null); }}>{sidebarMenuConversation.project_id ? "移动到其他项目" : "移到项目"}</button>
          {sidebarMenuConversation.project_id && <button type="button" role="menuitem" onClick={() => void moveConversationToProject(sidebarMenuConversation.id, null)}>移出项目</button>}
          <button type="button" role="menuitem" onClick={() => requestArchiveConversation(sidebarMenuConversation)}>归档</button>
          <span className="sidebar-menu-divider" role="separator" />
          <button type="button" role="menuitem" onClick={() => void copyText(sidebarMenuConversation.id, "会话 ID 已复制")}>复制会话 ID</button>
          <button type="button" role="menuitem" onClick={() => void copyText(`${window.location.origin}${window.location.pathname}?conversation=${encodeURIComponent(sidebarMenuConversation.id)}`, "深度链接已复制")}>复制深度链接</button>
          <span className="sidebar-menu-divider" role="separator" />
          <button type="button" role="menuitem" onClick={() => { const title = sidebarMenuConversation.title; newConversation(); setDraft(`继续“${title}”中的工作：`); setSidebarMenu(null); }}>在新会话中继续</button>
        </div>}
        {sidebarMenuProject && <div ref={sidebarMenuRef} className="sidebar-context-menu sidebar-project-context-menu" data-sidebar-menu role="menu" style={{ top: sidebarMenu?.top }}>
          <button type="button" role="menuitem" onClick={() => void toggleProjectPinned(sidebarMenuProject)}><UiIcon name="pin" /><span>{sidebarMenuProject.pinned_at ? "取消置顶项目" : "置顶项目"}</span></button>
          <button type="button" role="menuitem" onClick={() => { setProjectDialog(buildProjectDialogStateForEdit(sidebarMenuProject.id)); setSidebarMenu(null); }}><UiIcon name="edit" /><span>编辑项目</span></button>
          <button type="button" role="menuitem" onClick={() => requestArchiveProjectTasks(sidebarMenuProject)}><UiIcon name="archive" /><span>归档任务</span></button>
          <span className="sidebar-menu-divider" role="separator" />
          <button type="button" className="danger" role="menuitem" onClick={() => requestRemoveProject(sidebarMenuProject)}><UiIcon name="remove" /><span>移除</span></button>
        </div>}
      </aside>

      <button className="workspace-sidebar-scrim" type="button" aria-label="关闭侧栏" onClick={() => setSidebarOpen(false)} />

      <section className="workspace-stage" aria-label="AI 对话工作台">
        <header className="workspace-topbar">
          <button className="mobile-sidebar-trigger" type="button" aria-label="打开侧栏" onClick={() => setSidebarOpen(true)}>☰</button>
          <div className="workspace-title-block"><strong>{activeConversation?.title || (activeProjectId ? bootstrap.projects.find((item) => item.id === activeProjectId)?.name : null) || c.newConversation}</strong><small>{environmentLabel(me)} · {selectedScopeLabel}</small></div>
          <time className="workspace-topbar-date" dateTime={new Date().toISOString()}>{localizedDate(languagePreference, me.user.timezone)}</time>
          <div className="workspace-topbar-actions"><button className="topbar-scope-button" type="button" onClick={() => setActivePanel("scope")}>数据状态</button><button className="topbar-refresh-button" type="button" aria-label="刷新工作台" onClick={() => void onReload()}>↻</button><button className="topbar-new-button" type="button" aria-label="新建会话" onClick={() => newConversation()}>＋</button></div>
        </header>
        <main id="main-content" className="workspace-main">
          {activeConversationId ? (
            <ProductionConversation
              conversation={activeConversation}
              messages={messages}
              loading={messagesLoading}
              error={messagesError}
              draft={draft}
              setDraft={setDraft}
              sending={sending}
              onKeyDown={handleComposerKeyDown}
              onSubmit={submit}
              organizationUnits={organizationUnits}
              organizationScope={selectedOrganizationScope}
              setOrganizationScope={setSelectedOrganizationScope}
              authorizedModels={bootstrap.authorizedModels}
              selectedModelId={selectedModelId}
              setSelectedModelId={(modelId) => void changeSelectedModel(modelId)}
              language={languagePreference}
              disclaimer={c.disclaimer}
              jobs={bootstrap.jobs}
              onCancelAnswer={(messageId) => void cancelAnswer(messageId)}
              onRetryAnswer={(messageId) => void retryAnswer(messageId)}
            />
          ) : (
            <ProductionHome
              me={me}
              language={languagePreference}
              salutation={profilePreferences.salutation}
              organizationUnits={organizationUnits}
              organizationScope={selectedOrganizationScope}
              setOrganizationScope={setSelectedOrganizationScope}
              authorizedModels={bootstrap.authorizedModels}
              selectedModelId={selectedModelId}
              setSelectedModelId={(modelId) => void changeSelectedModel(modelId)}
              dailyBrief={dailyBrief}
              dailyBriefStatus={dailyBriefStatus}
              dataCapabilities={dataCapabilities}
              onOpenReport={() => void openReport("daily", latestDailyReport?.id)}
              draft={draft}
              setDraft={setDraft}
              sending={sending}
              onKeyDown={handleComposerKeyDown}
              onSubmit={submit}
              activeProjectName={activeProjectId ? bootstrap.projects.find((item) => item.id === activeProjectId)?.name ?? null : null}
            />
          )}
        </main>
      </section>

      {activePanel && <WorkspaceDetailPanel
        panel={activePanel}
        onClose={() => setActivePanel(null)}
        report={selectedReport}
        reportLoading={reportLoading}
        reports={bootstrap.reports}
        conversations={bootstrap.conversations}
        memories={bootstrap.memories}
        organizationUnits={organizationUnits}
        dataCapabilities={dataCapabilities}
        dailyBrief={dailyBrief}
        dailyBriefStatus={dailyBriefStatus}
        language={languagePreference}
        memoryEnabled={memoryEnabled}
        setMemoryEnabled={(value) => void changeMemoryEnabled(value)}
        onSelectReport={(report) => void openReport(report.kind === "weekly" ? "weekly" : "daily", report.id)}
        onOpenConversation={(conversation) => void openConversation(conversation)}
        onNewConversation={() => newConversation()}
        onRenameConversation={renameConversation}
        onArchiveConversation={requestArchiveConversation}
        onCreateMemory={handleCreateMemory}
        onUpdateMemory={handleUpdateMemory}
        onDeleteMemory={handleDeleteMemory}
      />}

      {preferencesView && <PreferencesWindow
        view={preferencesView}
        setView={setPreferencesView}
        onClose={() => setPreferencesView(null)}
        me={me}
        initials={userInitials}
        selectedScopeLabel={selectedScopeLabel}
        organizationUnits={organizationUnits}
        theme={themePreference}
        setTheme={setThemePreference}
        language={languagePreference}
        profilePreferences={profilePreferences}
        setProfilePreferences={saveProfilePreferences}
        memoryEnabled={memoryEnabled}
        setMemoryEnabled={(value) => void changeMemoryEnabled(value)}
        memories={bootstrap.memories}
        onCreateMemory={handleCreateMemory}
        onUpdateMemory={handleUpdateMemory}
        onDeleteMemory={handleDeleteMemory}
      />}

      {projectDialog && <ProjectDialog
        state={projectDialog}
        project={projectDialog.mode === "edit" ? bootstrap.projects.find((item) => item.id === projectDialog.projectId) ?? null : null}
        organizationUnits={organizationUnits}
        onClose={() => setProjectDialog(null)}
        onSave={(name, description, organizationUnitId) => saveProject(projectDialog, name, description, organizationUnitId)}
      />}
      {conversationProjectDialog && <ConversationProjectDialog
        conversation={bootstrap.conversations.find((item) => item.id === conversationProjectDialog.conversationId) ?? null}
        projects={sortedProjects}
        onClose={() => setConversationProjectDialog(null)}
        onMove={(projectId) => moveConversationToProject(conversationProjectDialog.conversationId, projectId)}
      />}
      {confirmState && <ConfirmDialog state={confirmState} onCancel={() => setConfirmState(null)} onConfirm={() => { const action = confirmState.action; setConfirmState(null); void action(); }} />}
      {toast && <Toast message={toast} />}
    </div>
  );
}
