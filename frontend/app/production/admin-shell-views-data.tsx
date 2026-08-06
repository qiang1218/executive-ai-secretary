"use client";

import { FormEvent, useEffect, useState } from "react";
import { humanizeApiError } from "./api-client";
import { productionServices } from "./services";
import type {
  DataOperationsV3Overview,
  DataSource,
  DataSyncRun,
  HarnessBusinessConfig,
  HarnessConfig,
  HarnessFastRule,
  HarnessMetrics,
  HarnessSimulation,
  HarnessTrace,
  HarnessVersion,
  McpToolCatalog,
  ScheduledTask,
} from "./types";
import {
  asRecord,
  atomicStatusLabel,
  copyHarnessConfig,
  DataOperationsView,
  dataSourceDisplayName,
  dataSourceTypeLabel,
  ExperienceWeightDraft,
  fieldTypeLabel,
  formatAdminTime,
  formatValidationAmount,
  harnessModuleGroups,
  harnessPromptFields,
  HarnessModule,
  shortHash,
  syncStatusLabel,
} from "./admin-shell-types";

export function DataOperationsPanel() {
  const [overview, setOverview] = useState<DataOperationsV3Overview | null>(null);
  const [sources, setSources] = useState<DataSource[]>([]);
  const [runs, setRuns] = useState<DataSyncRun[]>([]);
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeView, setActiveView] = useState<DataOperationsView>("sources");
  const [confirmSourceId, setConfirmSourceId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [weightDraft, setWeightDraft] = useState<ExperienceWeightDraft>({ high: 20, medium: 10, low: 5, notes: "" });

  async function load() {
    const [overviewResult, sourceResult, runResult, taskResult] = await Promise.all([
      productionServices.adminData.overview(),
      productionServices.adminData.sources(),
      productionServices.adminData.runs(),
      productionServices.adminData.scheduledTasks(),
    ]);
    setOverview(overviewResult);
    setSources(sourceResult.items);
    setRuns(runResult.items);
    setTasks(taskResult.items);
    setSelectedRunId((current) => current || runResult.items[0]?.id || "");
    setWeightDraft({
      high: overviewResult.experience_weight_policy.weights_json.high * 100,
      medium: overviewResult.experience_weight_policy.weights_json.medium * 100,
      low: overviewResult.experience_weight_policy.weights_json.low * 100,
      notes: overviewResult.experience_weight_policy.notes ?? "",
    });
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      productionServices.adminData.overview(),
      productionServices.adminData.sources(),
      productionServices.adminData.runs(),
      productionServices.adminData.scheduledTasks(),
    ]).then(([overviewResult, sourceResult, runResult, taskResult]) => {
      if (!active) return;
      setOverview(overviewResult);
      setSources(sourceResult.items);
      setRuns(runResult.items);
      setTasks(taskResult.items);
      setSelectedRunId(runResult.items[0]?.id ?? "");
      setWeightDraft({
        high: overviewResult.experience_weight_policy.weights_json.high * 100,
        medium: overviewResult.experience_weight_policy.weights_json.medium * 100,
        low: overviewResult.experience_weight_policy.weights_json.low * 100,
        notes: overviewResult.experience_weight_policy.notes ?? "",
      });
    }).catch((loadError: unknown) => {
      if (active) setError(humanizeApiError(loadError));
    });
    return () => { active = false; };
  }, []);

  async function perform(key: string, action: () => Promise<unknown>, success: string) {
    if (busy) return;
    setBusy(key);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
      setNotice(success);
    } catch (actionError) {
      setError(humanizeApiError(actionError));
    } finally {
      setBusy("");
    }
  }

  const latestRun = runs[0] ?? null;
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? latestRun;
  const enabledTasks = tasks.filter((task) => task.is_enabled).length;
  const tableBindings = overview?.sources.flatMap((source) => source.bindings) ?? [];
  const validatedBindings = tableBindings.filter((binding) => binding.validation_status === "validated").length;
  const latestSuccessful = overview?.sources.map((source) => source.latest_successful_run).filter((run): run is DataSyncRun => Boolean(run)).sort((left, right) => right.created_at.localeCompare(left.created_at))[0] ?? null;
  const latestRejected = overview?.sources.map((source) => source.latest_rejected_run).filter((run): run is DataSyncRun => Boolean(run)).sort((left, right) => right.created_at.localeCompare(left.created_at))[0] ?? null;
  const qualityRun = selectedRun ?? latestSuccessful;
  const qualityValidation = asRecord(qualityRun?.cross_table_validation_json);
  const relationshipChecks = asRecord(qualityValidation.relationship_checks);
  const amountChecks = asRecord(qualityValidation.amount_checks);
  const qualityWarnings = [
    ...(Array.isArray(qualityValidation.warnings) ? qualityValidation.warnings : []),
    ...(Array.isArray(qualityValidation.quality_warnings) ? qualityValidation.quality_warnings : []),
  ].map(asRecord).filter((item) => typeof item.message === "string");

  async function saveWeightPolicy(event: FormEvent) {
    event.preventDefault();
    const policy = overview?.experience_weight_policy;
    if (!policy || busy) return;
    if ([weightDraft.high, weightDraft.medium, weightDraft.low].some((value) => !Number.isFinite(value) || value < 0 || value > 100)) {
      setError("经验权重必须在 0% 至 100% 之间。");
      return;
    }
    if (!(weightDraft.high >= weightDraft.medium && weightDraft.medium >= weightDraft.low)) {
      setError("经验权重必须满足高 ≥ 中 ≥ 低。");
      return;
    }
    await perform("policy:save", () => productionServices.adminData.updateExperienceWeightPolicy({
      base_version: policy.version,
      weights: {
        high: weightDraft.high / 100,
        medium: weightDraft.medium / 100,
        low: weightDraft.low / 100,
      },
      label: `经验权重口径 v${policy.version + 1}`,
      notes: weightDraft.notes.trim(),
    }), `经验权重口径已生成 v${policy.version + 1}，只影响后续新批次与回答。`);
  }

  return (
    <main className="production-admin-main data-operations-main">
      <header className="production-admin-heading">
        <div><p>经营数据</p><h1>经营数据接入与同步</h1><span>集中检查只读数据源、调度计划和同步批次，不在这里修改业务事实。</span></div>
        <span className={`production-admin-status ${latestRun?.status === "failed" || latestRun?.status === "rejected" ? "risk" : latestSuccessful ? "positive" : "quiet"}`}><i aria-hidden="true" />{latestSuccessful ? "经营数据可用" : latestRun ? `最近${syncStatusLabel(latestRun.status)}` : "等待首次同步"}</span>
      </header>

      <div className="data-operations-console">
        <aside className="data-operations-nav" aria-label="经营数据模块"><strong>功能模块</strong><button className={activeView === "sources" ? "active" : ""} type="button" onClick={() => setActiveView("sources")}><span>数据接入</span><small>经营数据源</small></button><button className={activeView === "runs" ? "active" : ""} type="button" onClick={() => setActiveView("runs")}><span>同步运行</span><small>完整批次与拒绝</small></button><button className={activeView === "schedule" ? "active" : ""} type="button" onClick={() => setActiveView("schedule")}><span>调度计划</span><small>每日执行时间</small></button><button className={activeView === "quality" ? "active" : ""} type="button" onClick={() => setActiveView("quality")}><span>数据质量</span><small>关系与金额校验</small></button><button className={activeView === "policy" ? "active" : ""} type="button" onClick={() => setActiveView("policy")}><span>指标口径</span><small>经验权重版本</small></button></aside>
        <div className="data-operations-content">

      <section className="data-operations-summary" aria-label="经营数据摘要">
        <div><small>已接入数据域</small><strong>{validatedBindings} / {tableBindings.length || 3}</strong><span>已完成字段与 Schema 校验</span></div>
        <div><small>已启用调度</small><strong>{enabledTasks}</strong><span>{tasks.length ? `共 ${tasks.length} 项` : "尚未配置"}</span></div>
        <div><small>当前数据批次</small><strong>{latestSuccessful?.source_batch_id ? shortHash(latestSuccessful.source_batch_id) : "—"}</strong><span>{latestSuccessful ? atomicStatusLabel(latestSuccessful.atomic_activation_status) : "尚未激活"}</span></div>
        <div><small>指标口径版本</small><strong>v{overview?.experience_weight_policy.version ?? "—"}</strong><span>高 {weightDraft.high}% · 中 {weightDraft.medium}% · 低 {weightDraft.low}%</span></div>
      </section>

      {error && <p className="anspire-error" role="alert">{error}</p>}
      {notice && <p className="anspire-notice" role="status">{notice}</p>}

      {activeView === "sources" && <section className="data-operations-section data-source-v3-section">
        <header><div><h2>经营数据接入</h2></div><p>一个完整批次，全部数据域通过后才允许生效</p></header>
        <div className="data-source-v3-list">
          {sources.map((source) => {
            const operations = overview?.sources.find((item) => item.source_id === source.id);
            return <article className="data-source-v3-card" key={source.id}>
              <header><div className="data-source-identity"><i className={source.last_test_status ?? "pending"} aria-hidden="true" /><span><strong>{dataSourceDisplayName(source.display_name)}</strong><small>{dataSourceTypeLabel(source.source_type)} · ODS Schema {operations?.schema_version ?? source.schema_version}</small></span></div><div className="data-source-v3-policy"><small>切换策略</small><strong>完整批次切换</strong></div><label className="switch" title="启用数据源"><input type="checkbox" checked={source.is_enabled} disabled={Boolean(busy)} onChange={(event) => void perform(`source:${source.id}:toggle`, () => productionServices.adminData.updateSource(source.id, { is_enabled: event.target.checked }), event.target.checked ? "数据源已启用。" : "数据源已停用。")} /><span aria-hidden="true" /></label></header>
              <div className="feishu-binding-list">
                {operations?.bindings.map((binding) => <div className="feishu-binding-row" key={binding.domain}>
                  <div className="feishu-binding-heading"><span className={`binding-state ${binding.validation_status}`} aria-hidden="true" /><div><strong>{binding.display_name}</strong><small>{binding.configured ? `${binding.app_token_masked ?? "Base"} · ${binding.table_id ?? "Table ID 未返回"}` : "尚未绑定飞书表"}</small></div></div>
                  <dl><div><dt>字段</dt><dd>{binding.fields.length} 项</dd></div><div><dt>记录</dt><dd>{binding.record_count?.toLocaleString("zh-CN") ?? "—"}</dd></div><div><dt>Schema 哈希</dt><dd><code>{shortHash(binding.schema_hash)}</code></dd></div><div><dt>内容哈希</dt><dd><code>{shortHash(binding.content_hash)}</code></dd></div></dl>
                  <span className={`binding-status ${binding.validation_status}`}>{binding.validation_status === "validated" ? "校验通过" : binding.validation_status === "rejected" ? "已拒绝" : binding.validation_status === "configured" ? "等待校验" : "未配置"}</span>
                  <details className="feishu-field-contract"><summary>字段契约</summary><div>{binding.fields.map((field) => <span key={field.field_id}><b>{field.field_name}</b><small>{fieldTypeLabel(field.field_type)}{field.required ? " · 必填" : ""}</small></span>)}</div>{binding.warnings.map((warning) => <p key={warning}>{warning}</p>)}</details>
                </div>)}
                {!operations && <p className="data-operations-empty">正在等待 ODS 3.0 绑定状态。</p>}
              </div>
              <footer className="data-source-v3-footer"><span>最近连接测试：{formatAdminTime(source.last_tested_at)}</span><div><button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={() => void perform(`source:${source.id}:test`, () => productionServices.adminData.testSource(source.id), "连接、只读权限与基础结构均已通过验证。")}>{busy === `source:${source.id}:test` ? "测试中…" : "测试连接"}</button><button className="secondary-button" type="button" disabled={Boolean(busy) || !source.is_enabled} onClick={() => void perform(`source:${source.id}:validate`, () => productionServices.adminData.validateSource(source.id), "已创建校验任务；本次不会切换当前经营数据。")}>{busy === `source:${source.id}:validate` ? "创建中…" : "校验但不生效"}</button><button className="primary-button" type="button" disabled={Boolean(busy) || !source.is_enabled} onClick={() => setConfirmSourceId(source.id)}>同步并切换批次</button></div></footer>
              {confirmSourceId === source.id && <div className="atomic-sync-confirmation" role="alertdialog" aria-label="确认同步并切换完整批次"><div><strong>确认创建正式同步任务？</strong><span>系统将读取当前经营数据源。只有字段、跨域关系与金额恒等式全部通过，才会一次性切换完整数据批次。</span></div><div><button type="button" className="secondary-button" onClick={() => setConfirmSourceId("")}>取消</button><button type="button" className="primary-button" disabled={Boolean(busy)} onClick={() => void perform(`source:${source.id}:sync`, () => productionServices.adminData.syncSource(source.id), "已创建正式同步任务；经营数据校验通过后将切换完整批次。").then(() => setConfirmSourceId(""))}>{busy === `source:${source.id}:sync` ? "创建中…" : "确认执行"}</button></div></div>}
              {source.last_test_error && <p className="data-source-error">{source.last_test_error}</p>}
            </article>;
          })}
          {!sources.length && <p className="data-operations-empty">尚未配置数据源。客户部署时需要先完成标准脱敏源库连接。</p>}
        </div>
      </section>}

      {activeView === "schedule" && <section className="data-operations-section">
        <header><div><h2>调度计划</h2></div><p>调度器只创建任务，数据由独立 Worker 处理</p></header>
        <div className="scheduled-task-list">
          {tasks.map((task) => <article key={task.id}><span className={`task-state ${task.is_enabled ? "enabled" : ""}`} aria-hidden="true" /><div><strong>{task.key}</strong><small>{task.cron_expression} · {task.timezone}</small></div><dl><div><dt>下次执行</dt><dd>{formatAdminTime(task.next_run_at)}</dd></div><div><dt>上次入队</dt><dd>{formatAdminTime(task.last_enqueued_at)}</dd></div></dl><button className="secondary-button" type="button" disabled={Boolean(busy) || !task.is_enabled} onClick={() => void perform(`task:${task.id}`, () => productionServices.adminData.runScheduledTask(task.id), "已按当前任务配置创建一次立即运行。")}>{busy === `task:${task.id}` ? "创建中…" : "运行一次"}</button></article>)}
          {!tasks.length && <p className="data-operations-empty">当前没有同步调度计划。</p>}
        </div>
      </section>}

      {activeView === "runs" && <section className="data-operations-section data-runs-v3-section">
        <header><div><h2>同步运行</h2></div><p>批次不可变，可复核成功与拒绝原因</p></header>
        <div className="batch-outcome-strip"><article><small>最近成功批次</small><strong>{latestSuccessful?.source_batch_id ? shortHash(latestSuccessful.source_batch_id) : "尚无"}</strong><span>{latestSuccessful ? `${formatAdminTime(latestSuccessful.activated_at)} · ${latestSuccessful.records_written} 条已激活` : "完成首次正式切换后显示"}</span></article><article className={latestRejected ? "risk" : ""}><small>最近拒绝批次</small><strong>{latestRejected?.source_batch_id ? shortHash(latestRejected.source_batch_id) : "无"}</strong><span>{latestRejected ? `${formatAdminTime(latestRejected.completed_at)} · ${latestRejected.error_code ?? "校验未通过"}` : "当前没有被拒绝的经营数据批次"}</span></article></div>
        <div className="data-sync-table" role="table" aria-label="最近数据同步运行">
          <div role="row"><span role="columnheader">状态</span><span role="columnheader">运行方式</span><span role="columnheader">商机 / 项目 / 回款</span><span role="columnheader">数据时间</span><span role="columnheader">完成时间</span></div>
          {runs.slice(0, 16).map((run) => <button type="button" role="row" aria-selected={selectedRun?.id === run.id} key={run.id} onClick={() => setSelectedRunId(run.id)}><span role="cell"><i className={`sync-run-state ${run.status}`} aria-hidden="true" />{syncStatusLabel(run.status)}<small>{atomicStatusLabel(run.atomic_activation_status)}</small></span><span role="cell">{run.trigger_type === "manual_validation" ? "仅校验" : run.trigger_type === "manual" ? "人工同步" : run.trigger_type}</span><span role="cell">{run.source_record_counts_json.opportunity ?? "—"} / {run.source_record_counts_json.delivery ?? "—"} / {run.source_record_counts_json.collection ?? "—"}</span><span role="cell">{formatAdminTime(run.source_data_as_of)}</span><span role="cell">{formatAdminTime(run.completed_at)}</span></button>)}
          {!runs.length && <p className="data-operations-empty">同步开始后，批次状态会在这里显示。</p>}
        </div>
        {selectedRun && <div className="selected-run-detail"><div><small>批次 ID</small><code>{selectedRun.source_batch_id ?? selectedRun.id}</code></div><div><small>数据集版本</small><strong>{selectedRun.dataset_version ?? "—"}</strong></div><div><small>切换结果</small><strong>{atomicStatusLabel(selectedRun.atomic_activation_status)}</strong></div><div><small>经验权重版本</small><strong>{selectedRun.experience_weight_policy_id ? shortHash(selectedRun.experience_weight_policy_id) : "未记录"}</strong></div>{qualityWarnings.length > 0 && <p className="warning">{qualityWarnings.length} 项兼容或身份变化提示，请在数据质量中复核。</p>}{selectedRun.error_message && <p>{selectedRun.error_message}</p>}</div>}
      </section>}

      {activeView === "quality" && <section className="data-operations-section data-quality-section data-quality-v3-section"><header><div><h2>数据质量</h2></div><p>逐项展示关系和金额校验，不折叠成单一分数</p></header>{qualityRun ? <>
        <div className="data-quality-metrics"><article><small>商机记录</small><strong>{qualityRun.source_record_counts_json.opportunity ?? 0}</strong><span>业务主键必须唯一</span></article><article><small>项目记录</small><strong>{qualityRun.source_record_counts_json.delivery ?? 0}</strong><span>必须关联赢单商机</span></article><article><small>回款记录</small><strong>{qualityRun.source_record_counts_json.collection ?? 0}</strong><span>必须关联项目与商机</span></article><article className={qualityValidation.valid === false ? "risk" : ""}><small>经营数据校验</small><strong>{qualityValidation.valid === true ? "通过" : qualityValidation.valid === false ? "拒绝" : "待校验"}</strong><span>{atomicStatusLabel(qualityRun.atomic_activation_status)}</span></article></div>
        <div className="data-quality-detail-grid"><section><small>跨表关联检查</small><h3>关系完整性</h3><dl>{Object.entries(relationshipChecks).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd className={value === "passed" ? "passed" : ""}>{value === "passed" ? "通过" : String(value)}</dd></div>)}</dl>{!Object.keys(relationshipChecks).length && <p>当前批次没有可展示的关系检查。</p>}</section><section><small>金额恒等式</small><h3>经营金额对账</h3><div className="financial-invariant-grid"><span><small>签约金额</small><strong>{formatValidationAmount(amountChecks.signed_amount)}</strong></span><span><small>项目合同额</small><strong>{formatValidationAmount(amountChecks.contract_amount)}</strong></span><span><small>回款应收额</small><strong>{formatValidationAmount(amountChecks.receivable_amount)}</strong></span><span><small>已回款</small><strong>{formatValidationAmount(amountChecks.collected_amount)}</strong></span><span><small>未回款</small><strong>{formatValidationAmount(amountChecks.outstanding_amount)}</strong></span></div><p>必须同时满足：签约额 = 合同额 = 应收额；应收额 = 已回款 + 未回款。</p></section></div>
        {qualityWarnings.length > 0 && <div className="data-quality-warning-list"><strong>需人工复核</strong><div>{qualityWarnings.map((warning, index) => <p key={`${String(warning.code ?? "warning")}-${index}`}><span>{String(warning.domain ?? "batch")}</span>{String(warning.message)}</p>)}</div></div>}
        <div className="hash-verification-list"><strong>批次哈希</strong>{(["opportunity", "delivery", "collection"] as const).map((domain) => <div key={domain}><span>{domain === "opportunity" ? "商机总览" : domain === "delivery" ? "项目交付" : "财务回款"}</span><code>Schema {shortHash(qualityRun.source_schema_hashes_json[domain])}</code><code>内容 {shortHash(qualityRun.source_content_hashes_json[domain])}</code></div>)}</div>
      </> : <p className="data-operations-empty">完成首次校验后，这里会显示跨域关系、金额与哈希。</p>}</section>}

      {activeView === "policy" && <section className="data-operations-section experience-policy-section"><header><div><h2>指标口径</h2></div><p>独立于 Harness Prompt，由经营计算层强制执行</p></header>{overview ? <form onSubmit={(event) => void saveWeightPolicy(event)}><div className="experience-policy-heading"><div><small>当前版本</small><strong>v{overview.experience_weight_policy.version}</strong><span>{overview.experience_weight_policy.label}</span></div><div><small>观察窗口</small><strong>{overview.experience_weight_policy.observation_windows_json.join(" / ")} 天</strong><span>只报告偏差，不自动调权</span></div><div><small>生效时间</small><strong>{formatAdminTime(overview.experience_weight_policy.activated_at)}</strong><span>每次保存生成不可变新版本</span></div></div><div className="experience-policy-editor"><label><span>高靠谱度</span><div><input type="number" min={0} max={100} step={1} value={weightDraft.high} onChange={(event) => setWeightDraft((current) => ({ ...current, high: Number(event.target.value) }))} /><b>%</b></div><small>当前默认 20%</small></label><label><span>中靠谱度</span><div><input type="number" min={0} max={100} step={1} value={weightDraft.medium} onChange={(event) => setWeightDraft((current) => ({ ...current, medium: Number(event.target.value) }))} /><b>%</b></div><small>当前默认 10%</small></label><label><span>低靠谱度</span><div><input type="number" min={0} max={100} step={1} value={weightDraft.low} onChange={(event) => setWeightDraft((current) => ({ ...current, low: Number(event.target.value) }))} /><b>%</b></div><small>当前默认 5%</small></label></div><label className="experience-policy-notes"><span>版本备注</span><textarea rows={3} maxLength={1000} value={weightDraft.notes} onChange={(event) => setWeightDraft((current) => ({ ...current, notes: event.target.value }))} placeholder="记录本次调整依据；不要填写客户敏感信息。" /></label><div className="experience-policy-note"><strong>这不是赢单概率</strong><p>经验权重预测 = 在途商机预估金额 × 当前靠谱度权重。赢单使用实际签约金额，搁置与归档不进入预测；模型不能自行改变该口径。</p></div><footer><span>保存只影响后续新同步批次和回答，历史证据继续保留原口径版本。</span><button className="primary-button" type="submit" disabled={Boolean(busy)}>{busy === "policy:save" ? "正在生成新版本…" : "保存为新版本"}</button></footer></form> : <div className="anspire-loading">正在读取指标口径…</div>}</section>}
        </div>
      </div>
    </main>
  );
}

export function HarnessPolicyPanel() {
  const [current, setCurrent] = useState<HarnessConfig | null>(null);
  const [draft, setDraft] = useState<HarnessBusinessConfig | null>(null);
  const [versions, setVersions] = useState<HarnessVersion[]>([]);
  const [metrics, setMetrics] = useState<HarnessMetrics | null>(null);
  const [traces, setTraces] = useState<HarnessTrace[]>([]);
  const [mcpCatalog, setMcpCatalog] = useState<McpToolCatalog | null>(null);
  const [question, setQuestion] = useState("本月华东与华南的回款差距主要来自哪些客户？");
  const [simulation, setSimulation] = useState<HarnessSimulation | null>(null);
  const [busy, setBusy] = useState<"save" | "simulate" | "restore" | "" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeModule, setActiveModule] = useState<HarnessModule>("rewrite");

  async function load() {
    const [configResult, versionResult, metricResult, traceResult, toolResult] = await Promise.all([
      productionServices.adminHarness.get(),
      productionServices.adminHarness.versions(),
      productionServices.adminHarness.metrics(),
      productionServices.adminHarness.traces(),
      productionServices.adminMcp.list(),
    ]);
    setCurrent(configResult);
    setDraft(copyHarnessConfig(configResult.config));
    setVersions(versionResult);
    setMetrics(metricResult);
    setTraces(traceResult);
    setMcpCatalog(toolResult);
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      productionServices.adminHarness.get(),
      productionServices.adminHarness.versions(),
      productionServices.adminHarness.metrics(),
      productionServices.adminHarness.traces(),
      productionServices.adminMcp.list(),
    ]).then(([configResult, versionResult, metricResult, traceResult, toolResult]) => {
      if (!active) return;
      setCurrent(configResult);
      setDraft(copyHarnessConfig(configResult.config));
      setVersions(versionResult);
      setMetrics(metricResult);
      setTraces(traceResult);
      setMcpCatalog(toolResult);
    }).catch((loadError: unknown) => {
      if (active) setError(humanizeApiError(loadError));
    });
    return () => { active = false; };
  }, []);

  function updatePrompt(key: keyof HarnessBusinessConfig["prompts"], value: string) {
    setDraft((existing) => existing ? { ...existing, prompts: { ...existing.prompts, [key]: value } } : existing);
  }

  function updateRule(index: number, values: Partial<HarnessFastRule>) {
    setDraft((existing) => existing ? {
      ...existing,
      fast_rules: existing.fast_rules.map((rule, ruleIndex) => ruleIndex === index ? { ...rule, ...values } : rule),
    } : existing);
  }

  function addRule() {
    setDraft((existing) => existing ? {
      ...existing,
      fast_rules: [...existing.fast_rules, {
        id: `rule-${Date.now()}`,
        name: "新规则",
        enabled: true,
        priority: 50,
        match_mode: "any",
        terms: ["关键词"],
        exclusions: [],
        route: "data",
        candidate_tools: [],
      }],
    } : existing);
  }

  function toggleCandidateTool(ruleIndex: number, toolName: string) {
    if (!draft) return;
    const rule = draft.fast_rules[ruleIndex];
    const selected = rule.candidate_tools.includes(toolName);
    if (!selected && rule.candidate_tools.length >= 4) {
      setError("每条快速规则最多选择 4 个候选 MCP 工具。");
      return;
    }
    updateRule(ruleIndex, {
      candidate_tools: selected
        ? rule.candidate_tools.filter((name) => name !== toolName)
        : [...rule.candidate_tools, toolName],
    });
  }

  async function save() {
    if (!current || !draft || busy) return;
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const result = await productionServices.adminHarness.update(current.version, draft);
      setCurrent(result);
      setDraft(copyHarnessConfig(result.config));
      setVersions(await productionServices.adminHarness.versions());
      setNotice(`版本 v${result.version} 已立即作用于新消息任务；运行中的任务保持原快照。`);
    } catch (saveError) {
      setError(humanizeApiError(saveError));
      await load().catch(() => undefined);
    } finally {
      setBusy("");
    }
  }

  async function simulate() {
    if (!draft || !question.trim() || busy) return;
    setBusy("simulate");
    setError("");
    setNotice("");
    try {
      setSimulation(await productionServices.adminHarness.simulate(question.trim(), draft));
    } catch (simulationError) {
      setError(humanizeApiError(simulationError));
    } finally {
      setBusy("");
    }
  }

  async function restore(version: HarnessVersion) {
    if (busy || version.is_active) return;
    if (!window.confirm(`恢复 v${version.version} 的配置？恢复会生成一个新的当前版本。`)) return;
    setBusy("restore");
    setError("");
    try {
      const result = await productionServices.adminHarness.restore(version.id);
      setCurrent(result);
      setDraft(copyHarnessConfig(result.config));
      setVersions(await productionServices.adminHarness.versions());
      setNotice(`已从 v${version.version} 恢复并生成 v${result.version}。`);
    } catch (restoreError) {
      setError(humanizeApiError(restoreError));
    } finally {
      setBusy("");
    }
  }

  const dirty = Boolean(current && draft && JSON.stringify(current.config) !== JSON.stringify(draft));
  const plannerTools = mcpCatalog?.tools.filter((tool) => tool.is_enabled && tool.planner_enabled) ?? [];
  const activePrompt = harnessPromptFields.find((field) => field.key === activeModule) ?? null;

  return (
    <main className="production-admin-main harness-admin-main">
      <header className="production-admin-heading">
        <div><p>编排策略</p><h1>可运营 Harness</h1><span>选择一个模块专注编辑；权限、工具白名单与证据约束由安全内核强制执行。</span></div>
        <div className="production-admin-heading-actions"><span className="production-admin-status positive"><i aria-hidden="true" />{current ? `当前 v${current.version}` : "正在读取"}</span><button className="secondary-button" type="button" onClick={() => setActiveModule("simulate")}>运行模拟</button></div>
      </header>

      {!draft || !current ? <div className="anspire-loading">正在读取编排策略…</div> : <>
        <section className="harness-safety-strip">
          <div><small>不可编辑安全内核</small><strong>服务端权限 · 注册工具白名单 · 数据回答强制证据</strong></div>
          <span>最多 4 次工具调用 · 并发 3 · 修正规划 1 次 · 禁止联网、文件与任意代码</span>
        </section>

        <div className="harness-console">
          <aside className="harness-module-nav" aria-label="编排策略模块">
            <strong>编辑模块</strong>
            {harnessModuleGroups.map((group) => <section key={group.label}><small>{group.label}</small>{group.items.map((item) => <button className={activeModule === item.key ? "active" : ""} type="button" key={item.key} onClick={() => setActiveModule(item.key)}>{item.label}</button>)}</section>)}
          </aside>
          <section className="harness-module-canvas">
            {activePrompt && <div className="harness-prompt-editor"><header><div><small>当前 v{current.version} · 保存后只影响新任务</small><h2>{activePrompt.label}</h2><p>{activePrompt.note}；输出结构与权限范围不可由 Prompt 覆盖。</p></div><span>{draft.prompts[activePrompt.key].length.toLocaleString("zh-CN")} 字符</span></header><textarea aria-label={activePrompt.label} value={draft.prompts[activePrompt.key]} onChange={(event) => updatePrompt(activePrompt.key, event.target.value)} spellCheck={false} /><footer><code>{"{question}  {organization_scope}  {conversation_context}"}</code><span>安全变量由服务端按授权范围注入</span></footer></div>}

            {activeModule === "glossary" && <div className="harness-focused-section"><header><div><small>理解与规划</small><h2>业务术语表</h2><p>把企业内部表达映射为稳定业务含义，不改变指标口径。</p></div><button className="secondary-button" type="button" onClick={() => setDraft((existing) => existing ? { ...existing, glossary: [...existing.glossary, { term: "", canonical: "", category: "其他", enabled: true }] } : existing)}>新增术语</button></header><div className="harness-glossary focused">{draft.glossary.map((entry, index) => <div key={`${entry.term}-${index}`}><input aria-label="术语" value={entry.term} placeholder="术语" onChange={(event) => setDraft((existing) => existing ? { ...existing, glossary: existing.glossary.map((item, itemIndex) => itemIndex === index ? { ...item, term: event.target.value } : item) } : existing)} /><input aria-label="标准名称" value={entry.canonical} placeholder="标准名称" onChange={(event) => setDraft((existing) => existing ? { ...existing, glossary: existing.glossary.map((item, itemIndex) => itemIndex === index ? { ...item, canonical: event.target.value } : item) } : existing)} /><input aria-label="类别" value={entry.category} placeholder="类别" onChange={(event) => setDraft((existing) => existing ? { ...existing, glossary: existing.glossary.map((item, itemIndex) => itemIndex === index ? { ...item, category: event.target.value } : item) } : existing)} /><label className="switch"><input type="checkbox" checked={entry.enabled} onChange={(event) => setDraft((existing) => existing ? { ...existing, glossary: existing.glossary.map((item, itemIndex) => itemIndex === index ? { ...item, enabled: event.target.checked } : item) } : existing)} /><span aria-hidden="true" /></label><button type="button" aria-label="移除术语" onClick={() => setDraft((existing) => existing ? { ...existing, glossary: existing.glossary.filter((_, itemIndex) => itemIndex !== index) } : existing)}>×</button></div>)}</div></div>}

            {activeModule === "rules" && <div className="harness-focused-section"><header><div><small>规则与验证</small><h2>快速规则</h2><p>只加速高置信路由；查询改写、权限与证据校验始终执行。</p></div><button className="secondary-button" type="button" onClick={addRule}>新增规则</button></header><div className="harness-rule-list focused">{draft.fast_rules.map((rule, index) => <article key={rule.id}><header><label className="switch"><input type="checkbox" checked={rule.enabled} onChange={(event) => updateRule(index, { enabled: event.target.checked })} /><span aria-hidden="true" /></label><input value={rule.name} aria-label="规则名称" onChange={(event) => updateRule(index, { name: event.target.value })} /><span>优先级 <input type="number" min={0} max={1000} value={rule.priority} onChange={(event) => updateRule(index, { priority: Number(event.target.value) })} /></span><button type="button" aria-label="删除规则" onClick={() => setDraft((existing) => existing ? { ...existing, fast_rules: existing.fast_rules.filter((_, ruleIndex) => ruleIndex !== index) } : existing)}>×</button></header><div className="harness-rule-fields"><label><span>路由</span><select value={rule.route} onChange={(event) => updateRule(index, { route: event.target.value as HarnessFastRule["route"], candidate_tools: event.target.value === "general" ? [] : rule.candidate_tools })}><option value="data">经营问数</option><option value="general">个人泛化</option></select></label><label><span>匹配方式</span><select value={rule.match_mode} onChange={(event) => updateRule(index, { match_mode: event.target.value as HarnessFastRule["match_mode"] })}><option value="any">任一命中</option><option value="all">全部命中</option></select></label><label><span>关键词（逗号分隔）</span><input value={rule.terms.join("，")} onChange={(event) => updateRule(index, { terms: event.target.value.split(/[，,]/).map((item) => item.trim()).filter(Boolean) })} /></label><label><span>排除词（逗号分隔）</span><input value={rule.exclusions.join("，")} onChange={(event) => updateRule(index, { exclusions: event.target.value.split(/[，,]/).map((item) => item.trim()).filter(Boolean) })} /></label></div>{rule.route === "data" && <div className="harness-tool-picks"><span>候选 MCP（最多 4 个）</span>{plannerTools.map((tool) => <label key={tool.tool_name}><input type="checkbox" checked={rule.candidate_tools.includes(tool.tool_name)} onChange={() => toggleCandidateTool(index, tool.tool_name)} /><span>{tool.display_name}</span></label>)}</div>}</article>)}</div></div>}

            {activeModule === "simulate" && <div className="harness-focused-section"><header><div><small>规则与验证</small><h2>问题模拟与技术追踪</h2><p>模拟不调用经营工具；正式追踪默认只显示脱敏技术摘要。</p></div></header><div className="harness-validation-grid"><div className="harness-simulator"><label><span>示例问题</span><textarea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} /></label><button type="button" className="secondary-button" disabled={busy === "simulate" || !question.trim()} onClick={() => void simulate()}>{busy === "simulate" ? "正在模拟…" : "运行模拟"}</button>{simulation && <dl><div><dt>路由</dt><dd>{simulation.route}</dd></div><div><dt>来源</dt><dd>{simulation.route_source}{simulation.matched_rule_id ? ` · ${simulation.matched_rule_id}` : ""}</dd></div><div><dt>候选工具</dt><dd>{simulation.candidate_tools.join("、") || "无"}</dd></div><div><dt>歧义</dt><dd>{simulation.validation_issues.join("；") || "无"}</dd></div></dl>}</div><div className="harness-metrics"><strong>近 {metrics?.window_days ?? 30} 天</strong><div><span><b>{metrics?.message_count ?? 0}</b>消息任务</span><span><b>{Math.round((metrics?.structured_output_rate ?? 0) * 100)}%</b>结构有效</span><span><b>{Math.round((metrics?.tool_success_rate ?? 0) * 100)}%</b>工具成功</span></div><small>意图准确率需由基准集人工标注，不用线上自循环分数替代。</small></div></div><div className="harness-traces"><header><strong>最近技术追踪</strong><small>不显示问题、回答、个人记忆和业务正文</small></header>{traces.slice(0, 8).map((trace) => <article key={trace.message_id}><span className={`trace-route ${trace.route}`}>{trace.route ?? "—"}</span><div><strong>{trace.route_source ?? "unknown"} · v{trace.harness_version ?? "—"}</strong><small>{trace.organization_unit_count} 个事业部 · {trace.tools.join("、") || "未调用工具"}</small></div><span>{trace.stages.length} 阶段</span>{trace.diagnostic_shared_until && <i>已授权正文诊断</i>}</article>)}{!traces.length && <p>尚无正式任务追踪。</p>}</div></div>}

            {activeModule === "versions" && <div className="harness-focused-section"><header><div><small>规则与验证</small><h2>版本记录</h2><p>每次保存与恢复都会生成不可变版本，运行中的任务继续使用创建时快照。</p></div><code>{current.config_hash.slice(0, 12)}</code></header><section className="harness-version-rail focused"><div>{versions.slice(0, 12).map((version) => <article key={version.id}><span>v{version.version}</span><small>{new Date(version.activated_at).toLocaleString("zh-CN")}</small><code>{version.config_hash.slice(0, 10)}</code><button type="button" disabled={version.is_active || busy === "restore"} onClick={() => void restore(version)}>{version.is_active ? "当前" : "恢复"}</button></article>)}</div></section></div>}
          </section>
        </div>

        {error && <p className="anspire-error" role="alert">{error}</p>}
        {notice && <p className="anspire-notice" role="status">{notice}</p>}
        <div className="harness-save-bar"><span>{dirty ? "当前模块有尚未保存的策略修改" : `所有更改已保存 · v${current.version}`}</span><div><button type="button" className="secondary-button" disabled={!dirty || Boolean(busy)} onClick={() => setDraft(copyHarnessConfig(current.config))}>放弃</button><button type="button" className="secondary-button" disabled={busy === "simulate"} onClick={() => setActiveModule("simulate")}>先模拟</button><button type="button" className="primary-button" disabled={!dirty || Boolean(busy)} onClick={() => void save()}>{busy === "save" ? "正在校验并保存…" : "保存并生效"}</button></div></div>
      </>}
    </main>
  );
}
