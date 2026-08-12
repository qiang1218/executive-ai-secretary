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
import { AssistantOutputRenderer, parseAssistantOutput } from "./assistant-output";
import { loadProductionBootstrap, productionServices } from "./services";
import { looksLikeMarkdown, renderMarkdownToHtml } from "./markdown";
import { stageKey, useStageOutputs } from "./use-stage-outputs";
import type {
  AuthorizedModel,
  AuthMe,
  Conversation,
  ConversationMessage,
  DataCapabilities,
  DailyBrief,
  OrganizationScope,
  OrganizationUnit,
} from "./types";
import { UiIcon } from "./ui-icon";
import { useHumanGreeting } from "./use-human-greeting";
import {
  type DailyBriefLoadState,
  type UiLanguage,
  ALL_ORGANIZATIONS_SCOPE,
  COMPOSER_HINT_THRESHOLD,
  COMPOSER_MAX_LENGTH,
  copy,
  languageOptions,
} from "./workspace-types";
import {
  buildStructuredChart,
  dailyBriefDataAsOf,
  dailyBriefHeadline,
  domainLabels,
  findStructuredRows,
  formatTimestamp,
  humanizeMetricKey,
  messageStatusLabel,
  preferredDisplayName,
  professionalSourceLabel,
  scopeLabel,
  visibleStructuredEntries,
  formatStructuredValue,
  type StructuredChartDatum,
} from "./workspace-utils";

export function SidebarConversationRow({
  conversation,
  active,
  unread,
  renaming,
  renameDraft,
  setRenameDraft,
  onRename,
  onCancelRename,
  onOpen,
  onMenu,
}: {
  conversation: Conversation;
  active: boolean;
  unread: boolean;
  renaming: boolean;
  renameDraft: string;
  setRenameDraft: (value: string) => void;
  onRename: () => void;
  onCancelRename: () => void;
  onOpen: () => void;
  onMenu: (event: React.MouseEvent<HTMLButtonElement>) => void;
}) {
  return (
    <div className="sidebar-row-shell">
      {renaming ? (
        <form className="sidebar-rename-form" onSubmit={(event) => { event.preventDefault(); onRename(); }}>
          <input value={renameDraft} maxLength={60} onChange={(event) => setRenameDraft(event.target.value)} aria-label="新的会话名称" autoFocus />
          <button type="submit" aria-label="保存名称">✓</button>
          <button type="button" aria-label="取消重命名" onClick={onCancelRename}>×</button>
        </form>
      ) : (
        <>
          <button type="button" className={`sidebar-conversation-button ${active ? "active" : ""}`} onClick={onOpen}><span className={`sidebar-unread-dot ${unread ? "visible" : ""}`} aria-hidden="true" /><strong>{conversation.title || "未命名会话"}</strong></button>
          <button type="button" className="sidebar-row-menu-button" data-sidebar-menu aria-label={`打开“${conversation.title}”操作菜单`} onClick={onMenu}>•••</button>
        </>
      )}
    </div>
  );
}

export function ProductionHome({
  me,
  language,
  salutation,
  organizationUnits,
  organizationScope,
  setOrganizationScope,
  authorizedModels,
  selectedModelId,
  setSelectedModelId,
  dailyBrief,
  dailyBriefStatus,
  dataCapabilities,
  onOpenReport,
  draft,
  setDraft,
  sending,
  onKeyDown,
  onSubmit,
  activeProjectName,
}: {
  me: AuthMe;
  language: UiLanguage;
  salutation: string;
  organizationUnits: OrganizationUnit[];
  organizationScope: OrganizationScope;
  setOrganizationScope: (value: OrganizationScope) => void;
  authorizedModels: AuthorizedModel[];
  selectedModelId: string;
  setSelectedModelId: (value: string) => void;
  dailyBrief: DailyBrief | null;
  dailyBriefStatus: DailyBriefLoadState["status"];
  dataCapabilities: DataCapabilities | null;
  onOpenReport: () => void;
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent) => void;
  activeProjectName: string | null;
}) {
  const c = copy[language];
  const greeting = useHumanGreeting(me, language, salutation);
  const hasScope = organizationUnits.length > 0;
  const suggestions = c.suggestions;
  const dailyBriefAsOf = dailyBriefDataAsOf(dailyBrief);
  const briefTitle = dailyBrief
    ? dailyBriefHeadline(dailyBrief, language)
    : dailyBriefStatus === "loading" ? c.briefLoading : c.briefError;
  const briefMeta = dailyBrief
    ? dailyBriefAsOf
      ? `${c.briefDataThrough} ${formatTimestamp(dailyBriefAsOf, language)}`
      : c.briefDataPending
    : dailyBriefStatus === "loading" ? c.briefLoadingScope : c.briefErrorRetry;

  return (
    <div className="workspace-home">
      <div className="home-empty-stage">
        <div className="home-empty-inner">
          <div className="home-focus-group">
            <button className="morning-brief-trigger production-brief-trigger" type="button" onClick={() => dailyBrief && onOpenReport()} disabled={!dailyBrief}>
                <span className="morning-brief-dot" aria-hidden="true" />
                <span><strong>{briefTitle}</strong><small>{briefMeta}</small></span>
                <span>{c.briefViewReport} <b aria-hidden="true">›</b></span>
              </button>

            <section className="workspace-greeting" aria-labelledby="production-greeting-title">
              <div className="greeting-title-line"><span className="service-mark" aria-hidden="true" /><h1 id="production-greeting-title">{greeting}</h1></div>
              {!hasScope && <small className="active-project-context">经营数据尚未配置，仍可进行泛化问答。</small>}
              {activeProjectName && <small className="active-project-context">当前会话将归入项目：{activeProjectName}</small>}
            </section>

            <ProductionComposer
              id="production-home-question"
              language={language}
              draft={draft}
              setDraft={setDraft}
              sending={sending}
              disabled={false}
              organizationUnits={organizationUnits}
              organizationScope={organizationScope}
              setOrganizationScope={setOrganizationScope}
              authorizedModels={authorizedModels}
              selectedModelId={selectedModelId}
              setSelectedModelId={setSelectedModelId}
              onKeyDown={onKeyDown}
              onSubmit={onSubmit}
            />

            <section className="prompt-suggestions production-prompt-suggestions" aria-label={c.suggestionsAria}><div>{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => setDraft(suggestion)}><span>{suggestion}</span><i aria-hidden="true">›</i></button>)}</div></section>
          </div>
          <p className="home-service-note">{dataCapabilities?.source_kind.startsWith("simulated_") ? "当前使用演示模拟数据。" : dataCapabilities ? "经营数据已接入。" : "当前尚未激活经营数据。"}{c.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}

export function ProductionConversation({
  conversation,
  messages,
  loading,
  error,
  draft,
  setDraft,
  sending,
  onKeyDown,
  onSubmit,
  organizationUnits,
  organizationScope,
  setOrganizationScope,
  authorizedModels,
  selectedModelId,
  setSelectedModelId,
  language,
  disclaimer,
  jobs,
  onCancelAnswer,
  onRetryAnswer,
}: {
  conversation: Conversation | null;
  messages: ConversationMessage[];
  loading: boolean;
  error: string;
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent) => void;
  organizationUnits: OrganizationUnit[];
  organizationScope: OrganizationScope;
  setOrganizationScope: (value: OrganizationScope) => void;
  authorizedModels: AuthorizedModel[];
  selectedModelId: string;
  setSelectedModelId: (value: string) => void;
  language: UiLanguage;
  disclaimer: string;
  jobs: import("./types").Job[];
  onCancelAnswer: (messageId: string) => void;
  onRetryAnswer: (messageId: string) => void;
}) {
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  // messages 变化（流式 delta / tool_start / tool_complete / done）时自动滚到底部
  useEffect(() => {
    const node = chatScrollRef.current;
    if (!node) return;
    requestAnimationFrame(() => {
      node.scrollTo({ top: node.scrollHeight, behavior: messages.some((m) => m.status === "running") ? "auto" : "smooth" });
    });
  }, [messages]);

  return (
    <div className="chat-page production-chat-page">
      <div className="chat-scroll-region" ref={chatScrollRef}><div className="chat-scroll-inner"><div className="conversation-column">
        {loading && <MessageSkeleton />}
        {error && <section className="state-card" role="alert"><p className="eyebrow">加载失败</p><h3>暂时无法读取这条会话</h3><p>{error}</p></section>}
        {!loading && !error && !messages.length && <section className="chat-empty-state"><p className="eyebrow">空会话</p><h2>{conversation?.title || "新会话"}</h2><p>这条会话还没有消息，可以从下方输入框开始。</p></section>}
        {messages.map((message) => message.role === "system" && message.content_json?.event === "organization_scope_changed" ? (
          <div className="scope-change-divider" role="status" key={message.id}><span />{message.content}<span /></div>
        ) : message.role === "user" ? (
          <article className="user-message" key={message.id}><span>您</span><p>{message.content}</p><time>{formatTimestamp(message.created_at, language)}</time></article>
        ) : (
          <article className={`structured-answer production-answer ${message.status === "failed" ? "failed" : ""}`} key={message.id}>
            <div className="answer-meta"><span>{message.role === "assistant" ? "AI 秘书" : message.role === "tool" ? "数据工具" : "系统"}</span><time>{formatTimestamp(message.created_at, language)}</time></div>
            <AssistantMessageBody
              conversationId={conversation?.id ?? message.conversation_id}
              message={message}
              onFollowUp={setDraft}
            />
            {message.status && message.status !== "completed" && <small className={`message-status ${message.status}`}>状态：{messageStatusLabel(message.status)}</small>}
            <MessageJobActions
              message={message}
              job={jobs.find((item) => String(item.payload_json.assistant_message_id || "") === message.id)}
              onCancel={() => onCancelAnswer(message.id)}
              onRetry={() => onRetryAnswer(message.id)}
            />
          </article>
        ))}
      </div></div></div>
      <div className="workspace-composer-dock chat-dock">
        <ProductionComposer
          id="production-chat-question"
          language={language}
          draft={draft}
          setDraft={setDraft}
          sending={sending}
          disabled={false}
          organizationUnits={organizationUnits}
          organizationScope={organizationScope}
          setOrganizationScope={setOrganizationScope}
          authorizedModels={authorizedModels}
          selectedModelId={selectedModelId}
          setSelectedModelId={setSelectedModelId}
          onKeyDown={onKeyDown}
          onSubmit={onSubmit}
        />
        <p>{disclaimer}</p>
      </div>
    </div>
  );
}

function AssistantMessageBody({
  conversationId,
  message,
  onFollowUp,
}: {
  conversationId: string;
  message: ConversationMessage;
  onFollowUp: (question: string) => void;
}) {
  const envelope = parseAssistantOutput(message.content_json?.assistant_output);
  const toolSteps = message.tool_steps;
  // 把 "无 envelope" 时整段 message.content 也按 Markdown 渲染并写入本地缓存，
  // 实现"刷新后允许阶段和阶段内容对视"。
  const conclusionFallback = useMemo(() => renderMarkdownToHtml(message.content), [message.content]);
  const outputs = useStageOutputs(
    conversationId || undefined,
    message.id,
    toolSteps,
    conclusionFallback,
  );
  // 把"最终结论"渲染的 markdown 写入 sessionStorage（仅在没有 envelope 时）
  useEffect(() => {
    if (envelope) return;
    if (!message.content) return;
    if (!looksLikeMarkdown(message.content)) return;
    outputs.setConclusion(conclusionFallback);
    // 只在内容变化时同步即可。outputs 来自 useStageOutputs，每次渲染稳定
    // 同一 messageId，因此结论渲染函数输出稳定就不会重复写。
  }, [envelope, message.content, conclusionFallback, outputs]);

  // 把每个 stage 自带的 stageData.output 镜像到 sessionStorage，以便"刷新后还能对齐"。
  // 刷新场景：tool_steps 是从消息详情接口加载的，stageData.output 不一定还包含已被前端
  // 消费掉的瞬时内容；本地缓存作为兜底，让用户重新展开执行进度时仍能看到阶段文本。
  const mirroredStagesRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!toolSteps) return;
    for (let i = 0; i < toolSteps.length; i += 1) {
      const step = toolSteps[i];
      if (step.kind !== "stage") continue;
      const raw = step.stageData?.output;
      if (typeof raw !== "string" || !raw.trim()) continue;
      const key = stageKey(step, i);
      if (mirroredStagesRef.current.has(key)) continue;
      const html = renderMarkdownToHtml(raw);
      if (!html) continue;
      mirroredStagesRef.current.add(key);
      // 仅当本地缓存为空时写入，避免覆盖正在流式累积的更新。
      if (!outputs.stageOutputs[key]) {
        outputs.setOutputForStage(step, i, html);
      }
    }
    // step 引用频繁变化，依赖 toolSteps 自身即可
  }, [toolSteps, outputs]);
  return (
    <>
      {toolSteps && toolSteps.length > 0 && (
        <details className="tool-steps" open={toolSteps.some((s) => s.status === "running")}>
          <summary className="tool-steps-summary">
            <span className="tool-steps-icon">{toolSteps.every((s) => s.status === "done") ? "✓" : "⏳"}</span>
            执行进度（{toolSteps.filter((s) => s.status === "done").length}/{toolSteps.length}）
          </summary>
          <ul className="tool-steps-list">
            {toolSteps.map((step, i) => {
              const isStage = step.kind === "stage";
              const stageKind = step.stageKind;
              // 阶段步骤的图标与文案
              let icon = step.status === "done" ? "✓" : "⋯";
              let label = step.name;
              if (isStage) {
                if (stageKind === "turn_start") icon = step.status === "done" ? "✓" : "▶";
                else if (stageKind === "turn_end") icon = "■";
                else if (stageKind === "step") icon = step.status === "done" ? "✓" : "⟳";
                else if (stageKind === "thinking") icon = step.status === "done" ? "✓" : "💭";
                else if (stageKind === "interim_assistant") icon = "💬";
                else if (stageKind === "status") icon = "ℹ";
                // turn_start 步骤附加耗时
                if (stageKind === "turn_start" && step.stageData?.duration_seconds != null) {
                  label = `${label} · ${step.stageData.duration_seconds}s`;
                }
                // step 步骤附加 prev_tool_names
                if (stageKind === "step" && Array.isArray(step.stageData?.prev_tool_names) && (step.stageData?.prev_tool_names as string[]).length > 0) {
                  label = `${label}（已调用：${(step.stageData!.prev_tool_names as string[]).join("、")}）`;
                }
              }
              // 阶段下挂的输出：本地缓存里有则展示；否则若 result 看起来像 markdown 也渲染一次。
              const cachedOutput = isStage ? outputs.stageOutputs[stageKey(step, i)] : undefined;
              const derivedOutput =
                !cachedOutput && !isStage && step.result && looksLikeMarkdown(step.result)
                  ? renderMarkdownToHtml(step.result)
                  : null;
              const stageOutputHtml = isStage ? cachedOutput : derivedOutput;
              return (
                <li
                  key={i}
                  className={`tool-step-item ${step.status} ${isStage ? "stage-step" : ""} ${stageKind ? `stage-${stageKind}` : ""}`}
                >
                  <span className="tool-step-status" aria-hidden="true">{icon}</span>
                  <span className="tool-step-name">{label}</span>
                  {!isStage && step.result && !stageOutputHtml && (
                    <span className="tool-step-result">{step.result.slice(0, 120)}</span>
                  )}
                  {stageOutputHtml && (
                    <div
                      className="stage-output"
                      // 已经 escapeHtml + 自实现 markdown 渲染器，safe
                      dangerouslySetInnerHTML={{ __html: stageOutputHtml }}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </details>
      )}
      {envelope
        ? <AssistantOutputRenderer envelope={envelope} onFollowUp={onFollowUp} />
        : (
          <section className="answer-conclusion">
            {looksLikeMarkdown(message.content)
              ? <div className="answer-conclusion-markdown" dangerouslySetInnerHTML={{ __html: outputs.conclusionHtml || conclusionFallback }} />
              : <p>{message.content || "正在等待真实处理结果…"}</p>}
          </section>
        )}
      <MessageDetails
        conversationId={conversationId}
        message={message}
        contractRendered={Boolean(envelope)}
      />
    </>
  );
}

function MessageJobActions({
  message,
  job,
  onCancel,
  onRetry,
}: {
  message: ConversationMessage;
  job?: import("./types").Job;
  onCancel: () => void;
  onRetry: () => void;
}) {
  if (!job) return null;
  if (
    (message.status === "queued" || message.status === "running")
    && (job.status === "queued" || job.status === "running")
  ) {
    return <div className="message-job-actions"><button type="button" onClick={onCancel}>停止处理</button></div>;
  }
  if (message.status === "failed" && (job.status === "failed" || job.status === "canceled")) {
    return <div className="message-job-actions"><button type="button" onClick={onRetry}>重新尝试</button></div>;
  }
  return null;
}

function MessageSkeleton() {
  return <section className="message-skeleton" aria-live="polite" aria-label="正在读取会话消息"><span /><span /><span /><span /></section>;
}

function StructuredBarChart({
  metricKey,
  items,
}: {
  metricKey: string;
  items: StructuredChartDatum[];
}) {
  const maximum = Math.max(...items.map((item) => Math.abs(item.value)), 0);
  return (
    <section className="answer-structured-chart" aria-label={`${humanizeMetricKey(metricKey)}对比图`}>
      <header><div><small>数据对比</small><strong>{humanizeMetricKey(metricKey)}</strong></div><span>前 {items.length} 项</span></header>
      <div>{items.map((item, index) => <article key={`${item.label}-${index}`}><span title={item.label}>{item.label}</span><i aria-hidden="true"><b style={{ width: `${maximum ? Math.max(3, Math.abs(item.value) / maximum * 100) : 0}%` }} /></i><strong>{formatStructuredValue(metricKey, item.value)}</strong></article>)}</div>
    </section>
  );
}

function MessageDetails({
  conversationId,
  message,
  contractRendered = false,
}: {
  conversationId: string;
  message: ConversationMessage;
  contractRendered?: boolean;
}) {
  const content = message.content_json && typeof message.content_json === "object" ? message.content_json : {};
  const metrics = Array.isArray(content.metrics) ? content.metrics.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object")) : [];
  const sections = Array.isArray(content.sections) ? content.sections.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object")) : [];
  const structuredData = content.structured_data && typeof content.structured_data === "object" && !Array.isArray(content.structured_data) ? content.structured_data as Record<string, unknown> : {};
  const structuredMetrics = Object.entries(structuredData)
    .filter(([, value]) => typeof value === "number" || typeof value === "string")
    .slice(0, 6);
  const structuredRows = findStructuredRows(structuredData);
  const structuredChart = Array.isArray(structuredRows) ? buildStructuredChart(structuredRows) : null;
  const freshness = Array.isArray(content.freshness) ? content.freshness.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object")) : [];
  const citations = message.citations ?? (Array.isArray(content.citations) ? content.citations.filter((item): item is { label: string; source: string; as_of?: string | null } => Boolean(item && typeof item === "object" && "label" in item && "source" in item)) : []);
  const clarificationId = typeof content.clarification_id === "string" ? content.clarification_id : null;
  const clarificationOptions = Array.isArray(content.options) ? content.options.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object")) : [];
  const evidenceCount = typeof content.evidence_count === "number" ? content.evidence_count : 0;
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceRows, setEvidenceRows] = useState<Awaited<ReturnType<typeof productionServices.conversations.evidence>>>([]);
  const [clarificationResolved, setClarificationResolved] = useState(false);
  const [clarificationLoading, setClarificationLoading] = useState(false);
  const [shareConfirmOpen, setShareConfirmOpen] = useState(false);
  const [shareExpiresAt, setShareExpiresAt] = useState<string | null>(null);
  const [shareBusy, setShareBusy] = useState(false);

  async function toggleEvidence() {
    const next = !evidenceOpen;
    setEvidenceOpen(next);
    if (!next || evidenceRows.length || evidenceLoading) return;
    setEvidenceLoading(true);
    try {
      setEvidenceRows(await productionServices.conversations.evidence(conversationId, message.id));
    } finally {
      setEvidenceLoading(false);
    }
  }

  async function resolveClarification(value: string) {
    if (!clarificationId || clarificationLoading) return;
    setClarificationLoading(true);
    try {
      await productionServices.conversations.resolveClarification(conversationId, clarificationId, value);
      setClarificationResolved(true);
    } finally {
      setClarificationLoading(false);
    }
  }

  async function shareDiagnostic() {
    if (shareBusy) return;
    setShareBusy(true);
    try {
      const result = await productionServices.conversations.shareDiagnostic(conversationId, message.id);
      setShareExpiresAt(result.expires_at);
      setShareConfirmOpen(false);
    } finally {
      setShareBusy(false);
    }
  }

  async function revokeDiagnosticShare() {
    if (shareBusy) return;
    setShareBusy(true);
    try {
      await productionServices.conversations.revokeDiagnosticShare(conversationId, message.id);
      setShareExpiresAt(null);
    } finally {
      setShareBusy(false);
    }
  }

  if (!metrics.length && !sections.length && !structuredMetrics.length && !Array.isArray(structuredRows) && !citations.length && !freshness.length && !clarificationId && !message.source_data_as_of && !message.model_name && message.role !== "assistant") return null;
  return (
    <div className="production-message-details">
      {!contractRendered && metrics.length > 0 && <dl className="answer-metric-grid">{metrics.slice(0, 6).map((metric, index) => <div key={`${String(metric.label)}-${index}`}><dt>{String(metric.label ?? "指标")}</dt><dd>{String(metric.value ?? "—")}</dd>{metric.note ? <small>{String(metric.note)}</small> : null}</div>)}</dl>}
      {!contractRendered && structuredMetrics.length > 0 && <dl className="answer-metric-grid">{structuredMetrics.map(([key, value]) => <div key={key}><dt>{humanizeMetricKey(key)}</dt><dd>{formatStructuredValue(key, value)}</dd></div>)}</dl>}
      {!contractRendered && structuredChart && <StructuredBarChart metricKey={structuredChart.metricKey} items={structuredChart.items} />}
      {!contractRendered && Array.isArray(structuredRows) && structuredRows.length > 0 && <div className="answer-structured-table">{structuredRows.slice(0, 12).map((row, index) => { const record: Record<string, unknown> = row && typeof row === "object" && !Array.isArray(row) ? row as Record<string, unknown> : { value: row }; return <article key={`${index}-${String(record.source_record_id ?? record.name ?? record.stage ?? record.bucket ?? record.organization_name ?? "row")}`}><span>{String(index + 1).padStart(2, "0")}</span><div>{visibleStructuredEntries(record).map(([key, value]) => <p key={key}><small>{humanizeMetricKey(key)}</small><strong>{formatStructuredValue(key, value)}</strong></p>)}</div></article>; })}</div>}
      {!contractRendered && sections.length > 0 && <div className="answer-section-list">{sections.slice(0, 8).map((section, index) => <section key={`${String(section.title)}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{String(section.title ?? "分析")}</strong>{section.content || section.detail ? <p>{String(section.content ?? section.detail)}</p> : null}</div></section>)}</div>}
      {clarificationId && !clarificationResolved && <section className="clarification-options"><small>请确认后继续</small><div>{clarificationOptions.map((option, index) => { const label = String(option.label ?? option.value ?? `选项 ${index + 1}`); const value = String(option.value ?? option.label ?? ""); return <button type="button" key={`${value}-${index}`} disabled={!value || clarificationLoading} onClick={() => void resolveClarification(value)}>{label}<span aria-hidden="true">›</span></button>; })}</div>{!clarificationOptions.length && <p>请在输入框中补充需要查询的事业部范围。</p>}</section>}
      {clarificationResolved && <p className="clarification-resolved">已确认范围，正在继续处理。</p>}
      {((!contractRendered && (freshness.length > 0 || citations.length > 0 || message.source_data_as_of)) || message.model_name) && <details className="answer-evidence"><summary>{contractRendered ? "处理信息" : "来源与数据时间"}</summary><dl>{!contractRendered && message.source_data_as_of && <div><dt>数据截至</dt><dd>{formatTimestamp(message.source_data_as_of)}</dd></div>}{!contractRendered && freshness.map((item, index) => <div key={`${String(item.domain)}-${index}`}><dt>{domainLabels[String(item.domain)] ?? String(item.domain ?? "数据")}</dt><dd>{professionalSourceLabel(String(item.source_display_name ?? "未知来源"))} · {formatTimestamp(typeof item.source_data_as_of === "string" ? item.source_data_as_of : null)} · {item.status === "fresh" ? "最新" : String(item.status ?? "")}</dd></div>)}{!contractRendered && citations.map((citation, index) => <div key={`${citation.source}-${index}`}><dt>{citation.label}</dt><dd>{citation.source}{citation.as_of ? ` · ${citation.as_of}` : ""}</dd></div>)}{message.model_name && <div><dt>处理模型</dt><dd>{message.model_name}</dd></div>}</dl></details>}
      {evidenceCount > 0 && <section className="numeric-evidence"><button type="button" onClick={() => void toggleEvidence()}><span>{evidenceOpen ? "收起数字依据" : `查看数字依据（${evidenceCount}）`}</span><i aria-hidden="true">{evidenceOpen ? "⌃" : "⌄"}</i></button>{evidenceOpen && <div>{evidenceLoading ? <small>正在读取受控证据…</small> : evidenceRows.map((evidence) => <article key={evidence.id}><header><strong>{domainLabels[evidence.domain] ?? evidence.domain}</strong><span>{professionalSourceLabel(evidence.source_display_name)}</span></header><p>数据截至 {formatTimestamp(evidence.source_data_as_of)}{evidence.dataset_version ? ` · ${evidence.dataset_version}` : ""}</p><small>{evidence.row_references_json.length ? `${evidence.row_references_json.length} 条源记录引用` : "聚合结果来自当前激活数据版本"}</small></article>)}</div>}</section>}
      {message.role === "assistant" && message.status === "completed" && <section className="diagnostic-share-control">
        {shareExpiresAt ? <><span>本次诊断已临时共享至 {formatTimestamp(shareExpiresAt)}</span><button type="button" disabled={shareBusy} onClick={() => void revokeDiagnosticShare()}>提前撤销</button></> : <button type="button" onClick={() => setShareConfirmOpen(true)}>共享本次诊断</button>}
        {shareConfirmOpen && <div className="diagnostic-share-confirm" role="alertdialog" aria-label="确认共享本次诊断"><strong>向管理员共享 24 小时？</strong><p>仅共享这条问题、改写、执行计划与回答；不会共享长期记忆或其他会话。</p><div><button type="button" disabled={shareBusy} onClick={() => setShareConfirmOpen(false)}>取消</button><button type="button" disabled={shareBusy} onClick={() => void shareDiagnostic()}>{shareBusy ? "正在授权…" : "确认共享"}</button></div></div>}
      </section>}
    </div>
  );
}

export function ProductionComposer({
  id,
  language,
  draft,
  setDraft,
  sending,
  disabled,
  organizationUnits,
  organizationScope,
  setOrganizationScope,
  authorizedModels,
  selectedModelId,
  setSelectedModelId,
  onKeyDown,
  onSubmit,
}: {
  id: string;
  language: UiLanguage;
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  disabled: boolean;
  organizationUnits: OrganizationUnit[];
  organizationScope: OrganizationScope;
  setOrganizationScope: (value: OrganizationScope) => void;
  authorizedModels: AuthorizedModel[];
  selectedModelId: string;
  setSelectedModelId: (value: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const c = copy[language];
  const selectedModelIsAuthorized = authorizedModels.some((model) => model.model_id === selectedModelId);
  const selectedModelLabel = authorizedModels.find((model) => model.model_id === selectedModelId)?.display_name
    ?? (selectedModelId ? "原模型已取消授权" : "暂无可用模型");
  return (
    <form className="composer workbench-composer home-primary-composer production-composer" onSubmit={onSubmit}>
      <label className="sr-only" htmlFor={id}>输入经营问题</label>
      <textarea id={id} rows={2} maxLength={COMPOSER_MAX_LENGTH} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onKeyDown} placeholder={c.placeholder} disabled={disabled} />
      <div className="composer-footer">
        <div className="composer-tools">
          <OrganizationPicker language={language} units={organizationUnits} value={organizationScope} onChange={setOrganizationScope} disabled={!organizationUnits.length} />
        </div>
        <div className="composer-send">
          {draft.length >= COMPOSER_HINT_THRESHOLD && <span className="composer-character-count">{`${c.charsRemainingPrefix}${c.charsRemainingPrefix ? " " : ""}${(COMPOSER_MAX_LENGTH - draft.length).toLocaleString(language)} ${c.charsRemainingSuffix}`}</span>}
          <label className="composer-model-picker">
            <span className="sr-only">当前模型</span>
            <span className="composer-model-value" aria-hidden="true">{selectedModelLabel}</span>
            <span className="composer-model-chevron" aria-hidden="true">⌄</span>
            <select
              value={selectedModelId}
              disabled={!authorizedModels.length || sending}
              onChange={(event) => setSelectedModelId(event.target.value)}
              aria-label="选择本会话使用的模型"
            >
              {!authorizedModels.length && <option value="">管理员尚未授权模型</option>}
              {selectedModelId && !selectedModelIsAuthorized && (
                <option value={selectedModelId} disabled>原模型已取消授权，请重新选择</option>
              )}
              {authorizedModels.map((model) => (
                <option key={model.model_id} value={model.model_id}>{model.display_name}</option>
              ))}
            </select>
          </label>
          <button className="composer-submit-button" type="submit" disabled={disabled || sending || !draft.trim() || !selectedModelIsAuthorized} aria-label="发送问题">↑</button>
        </div>
      </div>
    </form>
  );
}

function OrganizationPicker({
  language,
  units,
  value,
  onChange,
  disabled,
}: {
  language: UiLanguage;
  units: OrganizationUnit[];
  value: OrganizationScope;
  onChange: (value: OrganizationScope) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [draftScope, setDraftScope] = useState<OrganizationScope>(value);
  const rootRef = useRef<HTMLDivElement>(null);
  const c = copy[language];
  const label = scopeLabel(value, units, language);
  const filtered = units.filter((unit) => unit.name.toLowerCase().includes(query.trim().toLowerCase()));
  const selectedIds = new Set(draftScope.mode === "selected" ? draftScope.organization_unit_ids : units.map((unit) => unit.id));
  const selectedCount = selectedIds.size;
  const allSelected = units.length > 0 && selectedCount === units.length;
  const someSelected = selectedCount > 0 && !allSelected;

  const closeWithoutApplying = useCallback(() => {
    setDraftScope(value);
    setQuery("");
    setOpen(false);
  }, [value]);

  function toggleOpen() {
    if (open) {
      closeWithoutApplying();
      return;
    }
    setDraftScope({ mode: value.mode, organization_unit_ids: [...value.organization_unit_ids] });
    setOpen(true);
  }

  function toggleUnit(unitId: string) {
    const next = new Set(selectedIds);
    if (next.has(unitId)) {
      next.delete(unitId);
    } else {
      next.add(unitId);
    }
    setDraftScope({ mode: "selected", organization_unit_ids: [...next] });
  }

  function toggleAll() {
    if (allSelected) {
      setDraftScope({ mode: "selected", organization_unit_ids: [] });
    } else {
      setDraftScope({ mode: "selected", organization_unit_ids: units.map((unit) => unit.id) });
    }
  }

  function apply() {
    if (selectedCount < 1) return;
    // 提交时，若全部选中则归一化为 all_authorized（保持后端语义）
    if (allSelected) {
      onChange(ALL_ORGANIZATIONS_SCOPE);
    } else {
      onChange({ mode: "selected", organization_unit_ids: [...selectedIds] });
    }
    setQuery("");
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) closeWithoutApplying();
    };
    const escape = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") closeWithoutApplying(); };
    window.addEventListener("pointerdown", close);
    window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("pointerdown", close); window.removeEventListener("keydown", escape); };
  }, [closeWithoutApplying, open]);

  return (
    <div ref={rootRef} className="organization-picker">
      <button type="button" className="composer-tool-button scope" disabled={disabled} aria-haspopup="dialog" aria-expanded={open} aria-label={`${label}，选择经营数据范围`} title={draftScope.mode === "selected" ? draftScope.organization_unit_ids.map((id) => units.find((unit) => unit.id === id)?.name).filter(Boolean).join("、") : c.scope} onClick={toggleOpen}><UiIcon name="organization" /><span>{label}</span><span className="organization-picker-chevron" aria-hidden="true">⌄</span></button>
      {open && <div className="organization-popover">
        <header><strong>{c.businessUnitScope}</strong></header>
        {units.length > 5 && <label className="organization-search"><UiIcon name="search" /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={c.searchBusinessUnits} autoFocus /></label>}
        <div className="organization-options" role="listbox" aria-multiselectable="true" aria-label="可分析事业部">
          <button type="button" role="option" aria-selected={allSelected} className={`organization-all-option ${allSelected ? "selected" : ""} ${someSelected ? "indeterminate" : ""}`} onClick={toggleAll}><span className="organization-check">{allSelected ? "✓" : someSelected ? "–" : ""}</span><span>{c.scope}</span></button>
          <div className="organization-divider" aria-hidden="true" />
          {filtered.map((unit) => <button type="button" role="option" aria-selected={selectedIds.has(unit.id)} className={selectedIds.has(unit.id) ? "selected" : ""} key={unit.id} onClick={() => toggleUnit(unit.id)}><span className="organization-check">{selectedIds.has(unit.id) ? "✓" : ""}</span><span>{unit.name}</span><UiIcon name="organization" /></button>)}
          {!filtered.length && <p className="organization-empty">没有匹配的事业部</p>}
        </div>
        <footer><small>可选范围由企业管理员配置</small><span>{selectedCount} / {units.length} 已选</span><button type="button" className="organization-apply" disabled={selectedCount < 1} onClick={apply}>{c.apply}</button></footer>
      </div>}
    </div>
  );
}
