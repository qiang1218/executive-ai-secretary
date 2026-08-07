"use client";

import {
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  AuthMe,
  Conversation,
  DataCapabilities,
  DailyBrief,
  Memory,
  OrganizationUnit,
  Report,
} from "./types";
import { UiIcon } from "./ui-icon";
import {
  type DailyBriefLoadState,
  type MemoryCreateHandler,
  type MemoryUpdateHandler,
  type PreferencesView,
  type ProfilePreferences,
  type ThemePreference,
  type UiLanguage,
  type WorkspacePanel,
  copy,
} from "./workspace-types";
import {
  dailyBriefDataAsOf,
  dailyBriefHeadline,
  dataStatusLabel,
  domainLabels,
  firstText,
  formatDate,
  formatTimestamp,
  preferredDisplayName,
  professionalSourceLabel,
  recordItems,
} from "./workspace-utils";
import { EmptyState } from "./workspace-dialogs";

export function WorkspaceDetailPanel({
  panel,
  onClose,
  report,
  reportLoading,
  reports,
  conversations,
  memories,
  organizationUnits,
  dataCapabilities,
  dailyBrief,
  dailyBriefStatus,
  language,
  memoryEnabled,
  setMemoryEnabled,
  onSelectReport,
  onOpenConversation,
  onNewConversation,
  onRenameConversation,
  onArchiveConversation,
  onCreateMemory,
  onUpdateMemory,
  onDeleteMemory,
}: {
  panel: WorkspacePanel;
  onClose: () => void;
  report: Report | null;
  reportLoading: boolean;
  reports: Report[];
  conversations: Conversation[];
  memories: Memory[];
  organizationUnits: OrganizationUnit[];
  dataCapabilities: DataCapabilities | null;
  dailyBrief: DailyBrief | null;
  dailyBriefStatus: DailyBriefLoadState["status"];
  language: UiLanguage;
  memoryEnabled: boolean;
  setMemoryEnabled: (value: boolean) => void;
  onSelectReport: (report: Report) => void;
  onOpenConversation: (conversation: Conversation) => void;
  onNewConversation: () => void;
  onRenameConversation: (conversationId: string, title: string) => Promise<void>;
  onArchiveConversation: (conversation: Conversation) => void;
  onCreateMemory: MemoryCreateHandler;
  onUpdateMemory: MemoryUpdateHandler;
  onDeleteMemory: (memory: Memory) => void;
}) {
  const titles: Record<WorkspacePanel, string> = {
    daily: "今日经营简报",
    weekly: "每周高层简报",
    history: "历史会话",
    memory: "长期记忆",
    scope: "可查询范围",
  };
  const reportPanel = panel === "daily" || panel === "weekly";
  return (
    <div className="workspace-panel-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className={`workspace-detail-panel ${reportPanel ? "report-detail-panel" : ""}`} role="dialog" aria-modal="true" aria-labelledby="production-panel-title">
        <header><div><h2 id="production-panel-title">{titles[panel]}</h2><small>工作台下钻</small></div><div className="panel-header-actions"><button type="button" className="panel-close-button" onClick={onClose} aria-label="关闭面板">×</button></div></header>
        <div className="workspace-detail-scroll">
          {panel === "daily"
            ? dailyBrief
              ? <ProductionDailyBriefPanel brief={dailyBrief} language={language} />
              : <div className="production-report-empty"><EmptyState title={dailyBriefStatus === "loading" ? "正在核对今日事项" : "晨间简报暂不可用"} description={dailyBriefStatus === "loading" ? "系统正在读取当前事业部范围的最新经营快照。" : "请先检查数据状态；系统不会使用其他事业部或历史样本替代当前范围。"} /></div>
            : reportPanel && <ProductionReportPanel kind={panel} report={report} loading={reportLoading} reports={reports} language={language} onSelectReport={onSelectReport} />}
          {panel === "history" && <ProductionHistoryPanel conversations={conversations} language={language} onOpen={onOpenConversation} onNew={onNewConversation} onRename={onRenameConversation} onArchive={onArchiveConversation} />}
          {panel === "memory" && <ProductionMemoryPanel memories={memories} organizationUnits={organizationUnits} enabled={memoryEnabled} setEnabled={setMemoryEnabled} onCreate={onCreateMemory} onUpdate={onUpdateMemory} onDelete={onDeleteMemory} />}
          {panel === "scope" && <ProductionScopePanel organizationUnits={organizationUnits} dataCapabilities={dataCapabilities} />}
        </div>
      </aside>
    </div>
  );
}

function ProductionHistoryPanel({
  conversations,
  language,
  onOpen,
  onNew,
  onRename,
  onArchive,
}: {
  conversations: Conversation[];
  language: UiLanguage;
  onOpen: (conversation: Conversation) => void;
  onNew: () => void;
  onRename: (conversationId: string, title: string) => Promise<void>;
  onArchive: (conversation: Conversation) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "pinned">("all");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return conversations
      .filter((item) => !item.archived_at)
      .filter((item) => filter === "all" || Boolean(item.pinned_at))
      .filter((item) => !normalized || item.title.toLowerCase().includes(normalized))
      .sort((first, second) => (second.last_message_at || second.updated_at).localeCompare(first.last_message_at || first.updated_at));
  }, [conversations, filter, query]);

  return (
    <div className="page subpage production-history-page">
      <section className="page-heading split"><div><p className="eyebrow">真实持久化</p><h1>历史会话</h1><p>恢复会话原有的数据范围与消息。重新提问时，系统仍按当前授权范围执行。</p></div><button type="button" className="primary-button" onClick={onNew}>新建会话</button></section>
      <section className="history-controls"><label><span className="sr-only">搜索历史会话</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索会话标题" /></label><div className="filter-tabs"><button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>全部</button><button type="button" className={filter === "pinned" ? "active" : ""} onClick={() => setFilter("pinned")}>已置顶</button></div><span>共 {filtered.length} 条</span></section>
      {filtered.length ? <div className="history-list">{filtered.map((conversation) => <article key={conversation.id}>
        {editingId === conversation.id ? <form onSubmit={(event) => { event.preventDefault(); void onRename(conversation.id, titleDraft).then(() => setEditingId(null)); }}><input value={titleDraft} maxLength={60} onChange={(event) => setTitleDraft(event.target.value)} autoFocus /><button type="submit">保存</button><button type="button" onClick={() => setEditingId(null)}>取消</button></form> : <button type="button" className="history-main" onClick={() => onOpen(conversation)}><span className="type-badge">{conversation.pinned_at ? "置顶" : "会话"}</span><span><strong>{conversation.title}</strong><small>{conversation.organization_unit_id ? "限定事业部范围" : "全部授权事业部"}</small></span><time>{formatTimestamp(conversation.last_message_at || conversation.updated_at, language)}</time></button>}
        <div className="history-actions"><button type="button" onClick={() => { setEditingId(conversation.id); setTitleDraft(conversation.title); }}>改名</button><button type="button" className="danger" onClick={() => onArchive(conversation)}>归档</button></div>
      </article>)}</div> : <EmptyState title="没有找到相关会话" description="换一个关键词或清除筛选条件。" action="清除筛选" onAction={() => { setQuery(""); setFilter("all"); }} />}
    </div>
  );
}

function ProductionMemoryPanel({
  memories,
  organizationUnits,
  enabled,
  setEnabled,
  onCreate,
  onUpdate,
  onDelete,
}: {
  memories: Memory[];
  organizationUnits: OrganizationUnit[];
  enabled: boolean;
  setEnabled: (value: boolean) => void;
  onCreate: MemoryCreateHandler;
  onUpdate: MemoryUpdateHandler;
  onDelete: (memory: Memory) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("preference");
  const [organizationUnitId, setOrganizationUnitId] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [editingContent, setEditingContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const kindLabels: Record<string, string> = { preference: "表达偏好", metric: "数字偏好", scope: "默认范围", focus: "长期关注", comparison: "比较口径" };

  async function submitNew(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !content.trim() || submitting) return;
    setSubmitting(true);
    const saved = await onCreate(title.trim(), content.trim(), kind, organizationUnitId || null);
    setSubmitting(false);
    if (!saved) return;
    setTitle("");
    setContent("");
    setKind("preference");
    setOrganizationUnitId("");
    setAdding(false);
  }

  return (
    <div className="page subpage production-memory-page">
      <section className="page-heading split"><div><p className="eyebrow">由您控制</p><h1>个人长期记忆</h1><p>只保存经确认的稳定偏好。记忆内容对企业管理员和实施人员保持正文隔离。</p></div><button type="button" className="secondary-button" onClick={() => setAdding(true)} disabled={!enabled}>手动新增</button></section>
      <section className="memory-master-setting"><div><strong>长期记忆</strong><p>{enabled ? "后续新消息可使用已确认的偏好。" : "已停止在界面中使用和新增，现有记忆仍保留。"}</p></div><label className="switch"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span aria-hidden="true" /><small>{enabled ? "已开启" : "已关闭"}</small></label></section>
      {adding && <form className="inline-form memory-add-form production-memory-form" onSubmit={submitNew}>
        <label className="field"><span>分类</span><select value={kind} onChange={(event) => setKind(event.target.value)}><option value="preference">表达偏好</option><option value="metric">数字偏好</option><option value="scope">默认范围</option><option value="focus">长期关注</option><option value="comparison">比较口径</option></select></label>
        <label className="field"><span>适用范围</span><select value={organizationUnitId} onChange={(event) => setOrganizationUnitId(event.target.value)}><option value="">全部授权范围</option>{organizationUnits.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label>
        <label className="field grow"><span>标题</span><input value={title} maxLength={240} onChange={(event) => setTitle(event.target.value)} placeholder="例如：经营会汇报偏好" /></label>
        <label className="field grow memory-content-field"><span>记忆内容</span><input value={content} maxLength={20000} onChange={(event) => setContent(event.target.value)} placeholder="例如：先给结论，再展开依据" /></label>
        <button type="submit" className="primary-button compact" disabled={!title.trim() || !content.trim() || submitting}>{submitting ? "保存中…" : "保存"}</button><button type="button" className="text-button" onClick={() => setAdding(false)}>取消</button>
      </form>}
      <section className="memory-list-section"><header className="section-header"><div><p className="eyebrow">{memories.length} 条</p><h2>已保存记忆</h2></div></header>
        {memories.length ? <div className="memory-list">{memories.map((memory) => {
          const unit = organizationUnits.find((item) => item.id === memory.organization_unit_id);
          return <article key={memory.id}><span className="type-badge">{kindLabels[memory.kind] || memory.kind}</span>
            {editingId === memory.id ? <form onSubmit={(event) => { event.preventDefault(); setSubmitting(true); void onUpdate(memory, { title: editingTitle.trim(), content: editingContent.trim() }).then((saved) => { setSubmitting(false); if (saved) setEditingId(null); }); }}><input value={editingTitle} maxLength={240} onChange={(event) => setEditingTitle(event.target.value)} /><textarea rows={3} value={editingContent} maxLength={20000} onChange={(event) => setEditingContent(event.target.value)} /><div><button type="submit" className="primary-button compact" disabled={!editingTitle.trim() || !editingContent.trim() || submitting}>保存</button><button type="button" className="text-button" onClick={() => setEditingId(null)}>取消</button></div></form> : <div className="memory-copy"><strong>{memory.title}</strong><p>{memory.content}</p><dl><div><dt>范围</dt><dd>{unit?.name || "全部授权范围"}</dd></div><div><dt>更新</dt><dd>{formatTimestamp(memory.updated_at)}</dd></div><div><dt>版本</dt><dd>v{memory.version}</dd></div></dl></div>}
            <div className="memory-actions"><button type="button" onClick={() => { setEditingId(memory.id); setEditingTitle(memory.title); setEditingContent(memory.content); }}>修改</button><button type="button" className="danger" onClick={() => onDelete(memory)}>删除</button></div>
          </article>;
        })}</div> : <EmptyState title="暂无长期记忆" description="明确表达并确认的稳定偏好会显示在这里。" />}
      </section>
    </div>
  );
}

function ProductionScopePanel({
  organizationUnits,
  dataCapabilities,
}: {
  organizationUnits: OrganizationUnit[];
  dataCapabilities: DataCapabilities | null;
}) {
  return (
    <div className="page subpage production-scope-page">
      <section className="page-heading"><p className="eyebrow">服务端授权结果</p><h1>可查询范围</h1><p>这里仅展示已经接入数据、已启用分析并且当前账号获准访问的事业部。前端不能自行添加。</p></section>
      <section className={`data-capability-summary ${dataCapabilities?.overall_status ?? "unavailable"}`}>
        <header><div><span className="status-dot" aria-hidden="true" /><div><strong>{dataStatusLabel(dataCapabilities)}</strong><small>{dataCapabilities ? professionalSourceLabel(dataCapabilities.source_label) : "尚未配置数据源"}</small></div></div><time>{dataCapabilities ? `状态生成于 ${formatTimestamp(dataCapabilities.generated_at)}` : "—"}</time></header>
        {dataCapabilities?.domains.length ? <div className="data-domain-grid">{dataCapabilities.domains.map((domain) => <article key={domain.domain}><span>{domainLabels[domain.domain] ?? domain.domain}</span><strong>{domain.record_count.toLocaleString("zh-CN")} 条</strong><small>数据截至 {formatTimestamp(domain.source_data_as_of)}</small><i className={domain.status}>{domain.status === "fresh" ? "最新" : domain.status === "stale" ? "较旧" : domain.status === "failed" ? "失败" : "部分可用"}</i>{domain.last_error_message && <p>{domain.last_error_message}</p>}</article>)}</div> : <p className="data-capability-empty">首次数据同步完成后，将按商机、交付、回款和目标分别展示状态。</p>}
      </section>
      {organizationUnits.length ? <div className="scope-unit-list">{organizationUnits.map((unit) => <article key={unit.id}><span className="scope-unit-mark" aria-hidden="true" /><div><strong>{unit.name}</strong><small>{unit.code} · {unit.unit_type}</small></div><span className="scope-unit-status">数据可用</span></article>)}</div> : <EmptyState title="尚未配置可分析事业部" description="请由企业管理员完成数据连接、启用分析并授予当前账号访问范围。" />}
      <aside className="scope-security-note"><UiIcon name="shield" /><div><strong>范围由服务端控制</strong><p>创建会话、生成任务和读取资源时都会再次校验权限，不依赖前端选择结果。</p></div></aside>
    </div>
  );
}

function ProductionDailyBriefPanel({ brief, language }: { brief: DailyBrief; language: UiLanguage }) {
  const c = copy[language];
  const asOf = dailyBriefDataAsOf(brief);
  const canConcludeNoItems = brief.readiness === "ready" || brief.readiness === "stale";
  const domainLabel = (domain: string) => domainLabels[domain] ?? domain;
  const readinessLabel = (readiness: string) => {
    if (language === "en") return readiness === "ready" ? "Ready" : readiness === "stale" ? "Older data" : readiness === "partial" ? "Partial" : "Unavailable";
    if (language === "zh-TW") return readiness === "ready" ? "已就緒" : readiness === "stale" ? "數據較早" : readiness === "partial" ? "部分可用" : "暫不可用";
    return readiness === "ready" ? "已就绪" : readiness === "stale" ? "数据较早" : readiness === "partial" ? "部分可用" : "暂不可用";
  };
  const metaLabel = c.briefMetaLabel;
  const explanation = c.briefExplanation;

  return (
    <article className="executive-report production-executive-report daily live-daily-brief">
      <header className="executive-report-lead">
        <div className="executive-report-meta">
          <div><span>{metaLabel}</span><time>{brief.brief_date ? formatDate(brief.brief_date, language) : "—"}</time></div>
          <p>{asOf ? `${c.dataThrough} ${formatTimestamp(asOf, language)}` : readinessLabel(brief.readiness)}</p>
        </div>
        <h1>{dailyBriefHeadline(brief, language)}</h1>
        <p>{explanation}</p>
      </header>

      {brief.items.length > 0 ? (
        <section className="live-daily-brief-items" aria-label={c.itemsAttention}>
          {brief.items.map((item) => (
            <article key={item.rule_id}>
              <span className="morning-brief-dot" aria-hidden="true" />
              <div><small>{domainLabel(item.domain)}</small><strong>{item.title}</strong><p>{item.detail}</p></div>
              <b>{item.affected_count}</b>
            </article>
          ))}
        </section>
      ) : canConcludeNoItems ? (
        <section className="live-daily-brief-clear"><span aria-hidden="true">✓</span><p>{c.noItemsClear}</p></section>
      ) : (
        <section className="live-daily-brief-clear uncertain"><span aria-hidden="true">!</span><p>{c.noItemsUncertain}</p></section>
      )}

      <details className="executive-report-provenance">
        <summary>{c.dataScopeReadiness}</summary>
        <dl>
          <div><dt>{c.scopeLabel}</dt><dd>{brief.uses_enterprise_snapshot ? c.allAuthorizedUnits : `${brief.organization_unit_ids.length}${c.unitCountSuffix}`}</dd></div>
          {brief.domains.map((domain) => <div key={domain.domain}><dt>{domainLabel(domain.domain)}</dt><dd>{readinessLabel(domain.readiness)} · {domain.record_count.toLocaleString(language)}{c.recordsSuffix}{domain.data_as_of ? ` · ${formatTimestamp(domain.data_as_of, language)}` : ""}</dd></div>)}
        </dl>
      </details>
    </article>
  );
}

function ProductionReportPanel({
  kind,
  report,
  loading,
  reports,
  language,
  onSelectReport,
}: {
  kind: "daily" | "weekly";
  report: Report | null;
  loading: boolean;
  reports: Report[];
  language: UiLanguage;
  onSelectReport: (report: Report) => void;
}) {
  const available = reports.filter((item) => item.kind === kind).sort((first, second) => second.period_end.localeCompare(first.period_end));
  if (loading) return <ReportSkeleton />;
  if (!report) return <div className="production-report-empty"><EmptyState title={kind === "daily" ? "尚无今日经营简报" : "尚无每周高层简报"} description="生产环境不会使用固定样本补位。配置经营数据与简报任务后，真实结果会显示在这里。" /></div>;

  const content = report.content ?? {};
  const summary = firstText(content, ["summary", "conclusion", "headline", "overview"]);
  const metrics = recordItems(content, ["metrics", "key_metrics", "indicators"]);
  const changes = recordItems(content, ["changes", "items", "sections", "attention_items", "findings"]);
  const actions = recordItems(content, ["actions", "action_items", "priorities", "recommendations"]);
  const attentionCount = typeof content.attention_items === "number" ? content.attention_items : changes.length;
  const sourceSummary = firstText(content, ["source_summary", "sources", "data_sources"]);
  const definition = firstText(content, ["definition", "methodology", "metric_definition"]);
  const reportLabel = kind === "daily" ? "每日经营变化" : "每周高层经营简报";

  return (
    <article className={`executive-report production-executive-report ${kind}`}>
      {available.length > 1 && <label className="report-version-select"><span>选择简报</span><select value={report.id} onChange={(event) => { const selected = available.find((item) => item.id === event.target.value); if (selected) onSelectReport(selected); }}>{available.map((item) => <option key={item.id} value={item.id}>{item.title} · {formatDate(item.period_end, language)}</option>)}</select></label>}
      <header className="executive-report-lead">
        <div className="executive-report-meta"><div><span>{reportLabel}</span><time>{kind === "daily" ? formatDate(report.period_end, language) : `${formatDate(report.period_start, language)}—${formatDate(report.period_end, language)}`}</time></div><p>{report.data_as_of ? `数据截至 ${formatTimestamp(report.data_as_of, language)}` : "尚未记录数据时间"}{report.published_at ? ` · ${formatTimestamp(report.published_at, language)} 发布` : ""}</p></div>
        <h1>{summary || report.title}</h1>
        <p>{summary ? report.title : "该版本已由正式简报服务创建；未写入的内容不会由前端自行补全。"}</p>
      </header>

      {metrics.length > 0 && <section className={`executive-metric-rail ${kind === "weekly" ? "weekly" : ""}`} aria-label="关键指标">{metrics.slice(0, kind === "weekly" ? 4 : 3).map((metric, index) => <div className="executive-report-metric" key={`${String(metric.label)}-${index}`}><span>{String(metric.label ?? metric.name ?? "指标")}</span><strong>{String(metric.value ?? "—")}</strong><small><i aria-hidden="true" />{String(metric.note ?? metric.change ?? "以简报版本为准")}</small></div>)}</section>}

      {changes.length > 0 && <section className="executive-report-section"><header><span>01—{String(changes.length).padStart(2, "0")}</span><h2>{kind === "daily" ? "关键变化" : "本周经营判断"}</h2></header><div className={`executive-change-list ${kind === "weekly" ? "weekly" : ""}`}>{changes.slice(0, 12).map((item, index) => <div className="executive-change-row" key={`${String(item.title)}-${index}`}><span className="executive-change-index">{String(index + 1).padStart(2, "0")}</span>{kind === "daily" && <span className="executive-change-status">{String(item.status ?? item.tone ?? "关注")}</span>}<span className="executive-change-copy"><strong>{String(item.title ?? item.label ?? `事项 ${index + 1}`)}</strong>{item.detail || item.content || item.description ? <small>{String(item.detail ?? item.content ?? item.description)}</small> : null}</span><span className="executive-change-arrow" aria-hidden="true">·</span></div>)}</div></section>}

      {(actions.length > 0 || attentionCount > 0) && <section className="executive-action-strip"><header><span>需要关注</span><h2>{kind === "daily" ? "需要确认" : "下一阶段优先事项"}</h2></header>{actions.length ? <ol>{actions.slice(0, 8).map((item, index) => <li key={`${String(item.title)}-${index}`}><span>{index + 1}</span><strong>{String(item.title ?? item.content ?? item.description ?? `事项 ${index + 1}`)}</strong></li>)}</ol> : <p className="report-attention-count">简报记录了 {attentionCount} 项待确认事项，但当前版本尚未写入可展示的明细。</p>}</section>}

      {!metrics.length && !changes.length && !actions.length && !summary && <section className="production-report-content-empty"><span aria-hidden="true">—</span><div><strong>简报正文尚未写入</strong><p>当前只有正式简报元数据。生产前端不会调用 Demo 样本补齐指标或结论。</p></div></section>}

      <details className="executive-report-provenance"><summary>数据范围、来源与生成信息</summary><dl><div><dt>范围</dt><dd>{report.organization_unit_id ? "限定事业部" : "全部授权事业部"}</dd></div><div><dt>周期</dt><dd>{formatDate(report.period_start, language)} 至 {formatDate(report.period_end, language)}</dd></div><div><dt>版本</dt><dd>{report.latest_version ? `v${report.latest_version}` : "尚无正文版本"}</dd></div>{sourceSummary && <div><dt>来源</dt><dd>{sourceSummary}</dd></div>}{definition && <div><dt>口径</dt><dd>{definition}</dd></div>}</dl></details>
    </article>
  );
}

function ReportSkeleton() {
  return <div className="report-skeleton" aria-live="polite" aria-label="正在读取简报"><span /><span /><span /><div><i /><i /><i /></div><span /><span /></div>;
}

export function PreferencesWindow({
  view,
  setView,
  onClose,
  me,
  initials,
  selectedScopeLabel,
  organizationUnits,
  theme,
  setTheme,
  language,
  profilePreferences,
  setProfilePreferences,
  memoryEnabled,
  setMemoryEnabled,
  memories,
  onCreateMemory,
  onUpdateMemory,
  onDeleteMemory,
}: {
  view: PreferencesView;
  setView: (view: PreferencesView) => void;
  onClose: () => void;
  me: AuthMe;
  initials: string;
  selectedScopeLabel: string;
  organizationUnits: OrganizationUnit[];
  theme: ThemePreference;
  setTheme: (theme: ThemePreference) => void;
  language: UiLanguage;
  profilePreferences: ProfilePreferences;
  setProfilePreferences: (value: ProfilePreferences) => Promise<boolean>;
  memoryEnabled: boolean;
  setMemoryEnabled: (value: boolean) => void;
  memories: Memory[];
  onCreateMemory: MemoryCreateHandler;
  onUpdateMemory: MemoryUpdateHandler;
  onDeleteMemory: (memory: Memory) => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(false);
  const [salutation, setSalutation] = useState(profilePreferences.salutation);
  const [amountUnit, setAmountUnit] = useState(profilePreferences.amountUnit);
  const [responseStyle, setResponseStyle] = useState(profilePreferences.responseStyle);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState("");
  const c = copy[language];
  const labels = {
    title: c.prefsTitle,
    back: c.prefsBack,
    profile: c.profile,
    appearance: c.appearance,
    memory: c.memory,
    close: c.prefsClose,
  };

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLElement>("button, input, select")?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  async function savePreferences(event: FormEvent) {
    event.preventDefault();
    setProfileSaving(true);
    setProfileError("");
    const saved = await setProfilePreferences({ salutation: salutation.trim() || "董事长", amountUnit, responseStyle });
    setProfileSaving(false);
    if (saved) setEditing(false);
    else setProfileError("暂时无法保存，请稍后重试。");
  }

  return (
    <div className="preferences-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} className="preferences-window" role="dialog" aria-modal="true" aria-labelledby="production-preferences-title">
        <aside className="preferences-sidebar">
          <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
          <button type="button" className="preferences-back" onClick={onClose}><span aria-hidden="true">←</span>{labels.back}</button>
          <div className="preferences-heading"><small>{labels.title}</small><strong id="production-preferences-title">{preferredDisplayName(me)}</strong></div>
          <nav aria-label={labels.title}>
            <button type="button" className={view === "profile" ? "active" : ""} onClick={() => setView("profile")}><UiIcon name="profile" /><span>{labels.profile}</span></button>
            <button type="button" className={view === "appearance" ? "active" : ""} onClick={() => setView("appearance")}><UiIcon name="appearance" /><span>{labels.appearance}</span></button>
            <button type="button" className={view === "memory" ? "active" : ""} onClick={() => setView("memory")}><UiIcon name="memory" /><span>{labels.memory}</span></button>
          </nav>
          <div className="preferences-privacy"><UiIcon name="shield" /><span><strong>仅您可见</strong><small>长期记忆正文不会向企业管理员展示</small></span></div>
        </aside>

        <main className="preferences-main">
          <header className="preferences-main-header"><div><small>{labels.title}</small><strong>{view === "profile" ? labels.profile : view === "appearance" ? labels.appearance : labels.memory}</strong></div><button type="button" onClick={onClose} aria-label={labels.close}>×</button></header>

          {view === "profile" && <div className="profile-settings-pane production-profile-pane">
            <section className="profile-hero"><span className="profile-hero-avatar" aria-hidden="true">{initials}</span><div><h1>{preferredDisplayName(me)}</h1><p>{profilePreferences.salutation} · {selectedScopeLabel}</p><small>{me.user.email}</small></div>{!editing && <button type="button" className="profile-edit-button" onClick={() => { setSalutation(profilePreferences.salutation); setAmountUnit(profilePreferences.amountUnit); setResponseStyle(profilePreferences.responseStyle); setEditing(true); }}><UiIcon name="edit" />编辑服务偏好</button>}</section>
            <section className="profile-summary-rail" aria-label="账号摘要"><div><small>专属称呼</small><strong>{profilePreferences.salutation}</strong><span>用于首页问候</span></div><div><small>可分析事业部</small><strong>{organizationUnits.length} 个</strong><span>由服务端授权决定</span></div><div><small>默认金额单位</small><strong>{profilePreferences.amountUnit === "yi" ? "亿元" : profilePreferences.amountUnit === "yuan" ? "元" : "万元"}</strong><span>用于回答表达</span></div></section>
            {editing ? <form className="profile-edit-form" onSubmit={(event) => void savePreferences(event)}><div className="profile-section-title"><span>编辑服务偏好</span><small>加密保存在您的个人配置中</small></div><div className="profile-form-grid"><label><span>专属称呼</span><input value={salutation} maxLength={24} onChange={(event) => setSalutation(event.target.value)} placeholder="例如：张总、Ryan" autoFocus /></label><label><span>默认金额单位</span><select value={amountUnit} onChange={(event) => setAmountUnit(event.target.value as ProfilePreferences["amountUnit"])}><option value="wan">万元</option><option value="yi">亿元</option><option value="yuan">元</option></select></label><label><span>回答风格</span><select value={responseStyle} onChange={(event) => setResponseStyle(event.target.value as ProfilePreferences["responseStyle"])}><option value="concise">简洁</option><option value="balanced">均衡</option><option value="detailed">详细</option></select></label></div>{profileError && <p className="anspire-error" role="alert">{profileError}</p>}<div className="profile-form-actions"><button type="button" disabled={profileSaving} onClick={() => setEditing(false)}>取消</button><button type="submit" disabled={profileSaving}>{profileSaving ? "正在保存…" : "保存偏好"}</button></div></form> : <div className="profile-detail-grid"><section><div className="profile-section-title"><span>服务偏好</span><small>仅您本人可读写</small></div><dl><div><dt>问候预览</dt><dd>早上好，{profilePreferences.salutation}</dd></div><div><dt>回答风格</dt><dd>{profilePreferences.responseStyle === "concise" ? "简洁" : profilePreferences.responseStyle === "detailed" ? "详细" : "均衡"}</dd></div><div><dt>金额表达</dt><dd>{profilePreferences.amountUnit === "yi" ? "亿元" : profilePreferences.amountUnit === "yuan" ? "元" : "万元"}</dd></div></dl></section><section><div className="profile-section-title"><span>账号与安全</span><small>正式身份信息</small></div><dl><div><dt>登录邮箱</dt><dd>{me.user.email}</dd></div><div><dt>角色</dt><dd>{me.user.role}</dd></div><div><dt>账号状态</dt><dd><span className="profile-status-dot" />正常</dd></div></dl></section></div>}
            <p className="production-profile-note">称呼、金额单位与回答偏好已迁移至服务端加密个人配置；企业管理员无法读取其正文。</p>
          </div>}

          {view === "appearance" && <div className="appearance-settings-pane"><header><p className="eyebrow">界面显示</p><h1>选择适合您的外观</h1><p>外观偏好只保存在当前设备，不影响会话、数据或长期记忆。</p></header><div className="appearance-options" role="radiogroup" aria-label="外观模式">{([
            ["system", "跟随系统", "随电脑的深浅色自动切换", "system"],
            ["light", "白天", "温暖克制的浅色工作台", "light"],
            ["dark", "夜间", "低眩光的深色工作台", "dark"],
          ] as const).map(([id, title, description, preview]) => <button type="button" role="radio" aria-checked={theme === id} className={theme === id ? "selected" : ""} key={id} onClick={() => setTheme(id)}><span className={`appearance-preview ${preview}`} aria-hidden="true"><span /><span /><span /></span><span className="appearance-option-copy"><i><UiIcon name={id} /></i><span><strong>{title}</strong><small>{description}</small></span></span><i className="appearance-radio" aria-hidden="true" /></button>)}</div><section className="appearance-composer-preview"><small>输入框预览</small><div><span>向 AI 秘书提问经营数据</span><i aria-hidden="true">↑</i></div><p>使用极轻的暖色阴影和清晰边界，保持克制的立体感。</p></section></div>}

          {view === "memory" && <div className="preferences-memory-pane"><ProductionMemoryPanel memories={memories} organizationUnits={organizationUnits} enabled={memoryEnabled} setEnabled={setMemoryEnabled} onCreate={onCreateMemory} onUpdate={onUpdateMemory} onDelete={onDeleteMemory} /></div>}
        </main>
      </div>
    </div>
  );
}
