"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { humanizeApiError } from "./api-client";
import { productionServices } from "./services";
import type {
  AdminModelAuthorization,
  AdminModelCatalog,
  McpTool,
  McpToolCatalog,
  ModelProviderConfig,
} from "./types";
import type { AdminView } from "./admin-shell-types";
import { guideContent } from "./admin-shell-types";

export function AdminGuide({ view, collapsed, onToggle }: { view: AdminView; collapsed: boolean; onToggle: () => void }) {
  const content = guideContent[view];
  return (
    <aside className="production-admin-guide" aria-label="当前页面说明">
      <button className="production-admin-guide-toggle" type="button" onClick={onToggle} aria-expanded={!collapsed} aria-label={collapsed ? "展开页面说明" : "收起页面说明"}><span aria-hidden="true">{collapsed ? "‹" : "›"}</span></button>
      {!collapsed && <div className="production-admin-guide-content"><small>{content.eyebrow}</small><h2>{content.title}</h2><p>{content.summary}</p><ol>{content.principles.map((item, index) => <li key={item}><span>{String(index + 1).padStart(2, "0")}</span>{item}</li>)}</ol><footer>说明栏仅解释当前功能，不影响任何运行配置。</footer></div>}
    </aside>
  );
}

export function ModelProviderPanel() {
  const [config, setConfig] = useState<ModelProviderConfig | null>(null);
  const [catalog, setCatalog] = useState<AdminModelCatalog | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modelSearch, setModelSearch] = useState("");
  const [modelView, setModelView] = useState<"all" | "authorized" | "pending">("all");

  useEffect(() => {
    let active = true;
    Promise.all([
      productionServices.adminModels.get(),
      productionServices.adminModels.catalog(),
    ])
      .then(([result, catalogResult]) => {
        if (!active) return;
        setConfig(result);
        setCatalog(catalogResult);
      })
      .catch((loadError: unknown) => {
        if (active) setError(humanizeApiError(loadError));
      });
    return () => { active = false; };
  }, []);

  async function reload() {
    const [result, catalogResult] = await Promise.all([
      productionServices.adminModels.get(),
      productionServices.adminModels.catalog(),
    ]);
    setConfig(result);
    setCatalog(catalogResult);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!config || busy) return;
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const next = await productionServices.adminModels.update({
        model_id: config.model_id,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
      });
      setConfig(next);
      setApiKey("");
      await reload();
      setNotice("网关凭证已加密保存。凭证发生变化后，各模型需要重新测试与授权。");
    } catch (saveError) {
      setError(humanizeApiError(saveError));
    } finally {
      setBusy(null);
    }
  }

  async function testModel(model: AdminModelAuthorization) {
    if (!config || busy) return;
    setBusy(`test:${model.model_id}`);
    setError("");
    setNotice("");
    try {
      const result = await productionServices.adminModels.testModel(model.model_id);
      await reload();
      setNotice(`${model.display_name} 测试通过，${result.latency_ms} ms。现在可以授权给董事长。`);
    } catch (testError) {
      setError(humanizeApiError(testError));
      await reload();
    } finally {
      setBusy(null);
    }
  }

  async function toggleAuthorization(model: AdminModelAuthorization) {
    if (!config || busy) return;
    setBusy(`authorize:${model.model_id}`);
    setError("");
    setNotice("");
    try {
      await productionServices.adminModels.authorize(
        model.model_id,
        !model.is_authorized,
        model.display_name,
      );
      await reload();
      setNotice(model.is_authorized ? `${model.display_name} 已取消授权。` : `${model.display_name} 已授权给董事长。`);
    } catch (toggleError) {
      setError(humanizeApiError(toggleError));
    } finally {
      setBusy(null);
    }
  }

  async function setDefault(model: AdminModelAuthorization) {
    if (busy || model.is_default) return;
    setBusy(`default:${model.model_id}`);
    setError("");
    setNotice("");
    try {
      await productionServices.adminModels.setDefault(model.model_id);
      await reload();
      setNotice(`${model.display_name} 已设为新会话默认模型。`);
    } catch (defaultError) {
      setError(humanizeApiError(defaultError));
    } finally {
      setBusy(null);
    }
  }

  const status = !config?.is_configured
    ? { label: "未配置", tone: "quiet" }
    : catalog?.models.some((item) => item.is_authorized)
      ? { label: `${catalog.models.filter((item) => item.is_authorized).length} 个模型已授权`, tone: "positive" }
      : { label: "等待模型授权", tone: "attention" };
  const visibleModels = (catalog?.models ?? [])
    .filter((model) => model.selectable)
    .filter((model) => modelView === "all"
      || (modelView === "authorized" ? model.is_authorized : !model.is_authorized))
    .filter((model) => {
      const query = modelSearch.trim().toLocaleLowerCase("zh-CN");
      return !query || [model.display_name, model.name, model.family, model.model_id]
        .some((value) => value.toLocaleLowerCase("zh-CN").includes(query));
    });

  return (
    <main className="production-admin-main">
      <header className="production-admin-heading">
        <div><p>模型服务</p><h1>Anspire 单一模型通道</h1><span>路由、规划与回答统一通过 Anspire；不接入其他模型供应商。</span></div>
        <span className={`production-admin-status ${status.tone}`}><i aria-hidden="true" />{status.label}</span>
      </header>
      <section className="anspire-provider-summary" aria-label="Anspire 接入边界">
        <div><small>服务商</small><strong>Anspire Open</strong></div>
        <div><small>正式网关</small><strong>open-gateway.anspire.ai</strong></div>
        <div><small>运行边界</small><strong>唯一生成模型通道</strong></div>
        <a href={config?.documentation_url ?? "https://llm.anspire.ai/?tab=models"} target="_blank" rel="noreferrer">查看官方模型列表 <span aria-hidden="true">↗</span></a>
      </section>
      <form className="anspire-settings-card" onSubmit={save}>
        <header><div><p>企业共享网关</p><h2>Anspire 凭证</h2></div><span>模型授权与凭证分离管理</span></header>
        {!config ? <div className="anspire-loading" aria-live="polite">正在读取企业模型配置…</div> : <>
          <div className="anspire-settings-grid">
            <label><span>API Key</span><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={config.api_key_masked ?? "输入 Anspire API Key"} autoComplete="off" spellCheck={false} /><small>{config.is_configured ? `已保存 ${config.api_key_masked}；留空不会替换。` : "保存后以企业独立密钥加密，页面不会再次返回明文。"}</small></label>
            <label className="wide"><span>API 接口</span><input value={config.endpoint_url} readOnly aria-readonly="true" /><small>地址由系统锁定，管理员不能改成其他兼容网关。</small></label>
            <label className="wide"><span>授权策略</span><input value="逐模型测试通过后，由管理员加入授权" readOnly aria-readonly="true" /><small>凭证只定义企业共享网关；默认模型和董事长可选范围在下方单独管理。</small></label>
          </div>
          {config.last_test_error && <p className="anspire-error" role="alert">{config.last_test_error}</p>}
          {error && <p className="anspire-error" role="alert">{error}</p>}
          {notice && <p className="anspire-notice" role="status">{notice}</p>}
          <footer><p>密钥不会写入浏览器存储、日志或回答证据；更换凭证会自动撤销旧测试结论。</p><div><button className="primary-button" type="submit" disabled={Boolean(busy)}>{busy === "save" ? "正在保存…" : "保存网关配置"}</button></div></footer>
        </>}
      </form>
      <section className="admin-model-authorization">
        <header><div><small>董事长可用模型</small><h2>测试与授权</h2><p>只有使用当前凭证测试成功的模型，才允许出现在董事长工作台。</p></div><span>{catalog?.credential_version ? `凭证版本 v${catalog.credential_version}` : "等待配置"}</span></header>
        {catalog && <div className="admin-model-directory-controls"><label><span className="sr-only">搜索模型</span><input type="search" value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} placeholder="搜索模型名称、系列或 ID" /></label><div role="group" aria-label="模型目录筛选"><button type="button" className={modelView === "all" ? "active" : ""} onClick={() => setModelView("all")}>全部</button><button type="button" className={modelView === "authorized" ? "active" : ""} onClick={() => setModelView("authorized")}>已授权</button><button type="button" className={modelView === "pending" ? "active" : ""} onClick={() => setModelView("pending")}>待评估</button></div><span>{visibleModels.length} 个模型</span></div>}
        {!catalog ? <div className="anspire-loading">正在读取模型授权目录…</div> : <div className="admin-model-list">{visibleModels.map((model) => {
          const testCurrent = model.test_status === "success" && model.tested_credential_version === model.current_credential_version;
          return <article key={model.model_id} className={model.is_authorized ? "authorized" : ""}><div className="admin-model-identity"><span className={`model-test-dot ${testCurrent ? "success" : model.test_status}`} aria-hidden="true" /><div><strong>{model.display_name}</strong><small>{model.family} · {model.model_id}</small></div></div><p>{model.profile}</p><div className="admin-model-state"><span>{testCurrent ? `${model.last_test_latency_ms ?? "—"} ms` : model.test_status === "failed" ? "测试失败" : model.tested_credential_version ? "凭证变更，需复测" : "尚未测试"}</span>{model.is_default && <b>默认</b>}{model.is_authorized && !model.is_default && <button type="button" disabled={Boolean(busy)} onClick={() => void setDefault(model)}>{busy === `default:${model.model_id}` ? "设置中…" : "设为默认"}</button>}</div><div className="admin-model-actions"><button className="secondary-button" type="button" disabled={Boolean(busy) || !config?.is_configured} onClick={() => void testModel(model)}>{busy === `test:${model.model_id}` ? "测试中…" : testCurrent ? "重新测试" : "测试模型"}</button><button className={model.is_authorized ? "secondary-button" : "primary-button"} type="button" disabled={Boolean(busy) || (!model.is_authorized && !testCurrent)} onClick={() => void toggleAuthorization(model)}>{busy === `authorize:${model.model_id}` ? "更新中…" : model.is_authorized ? "取消授权" : "加入授权"}</button></div></article>;
        })}{!visibleModels.length && <p className="data-operations-empty">没有符合当前筛选条件的模型。</p>}</div>}
      </section>
    </main>
  );
}

export function McpToolsPanel() {
  const [catalog, setCatalog] = useState<McpToolCatalog | null>(null);
  const [selectedName, setSelectedName] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState({ display_name: "", description: "", timeout_seconds: 20, max_rows: 50, operator_note: "" });
  const [createOpen, setCreateOpen] = useState(false);
  const [createDraft, setCreateDraft] = useState({ tool_name: "custom_", display_name: "", description: "", category: "综合经营", component_tools: [] as string[], operator_note: "" });

  async function loadCatalog(preferredToolName?: string) {
    const result = await productionServices.adminMcp.list();
    setCatalog(result);
    const next = result.tools.find((item) => item.tool_name === preferredToolName)
      ?? result.tools.find((item) => item.tool_name === selectedName)
      ?? result.tools[0];
    setSelectedName(next?.tool_name ?? "");
    if (next) {
      setDraft({
        display_name: next.display_name,
        description: next.description,
        timeout_seconds: next.timeout_seconds,
        max_rows: next.max_rows,
        operator_note: next.operator_note ?? "",
      });
    }
  }

  useEffect(() => {
    let active = true;
    productionServices.adminMcp.list().then((result) => {
        if (!active) return;
        setCatalog(result);
        const first = result.tools[0];
        setSelectedName(first?.tool_name ?? "");
        if (first) {
          setDraft({
            display_name: first.display_name,
            description: first.description,
            timeout_seconds: first.timeout_seconds,
            max_rows: first.max_rows,
            operator_note: first.operator_note ?? "",
          });
        }
      }).catch((loadError: unknown) => {
        if (active) setError(humanizeApiError(loadError));
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!createOpen) return;
    const previousOverflow = document.body.style.overflow;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) setCreateOpen(false);
    }
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [busy, createOpen]);

  const selected = catalog?.tools.find((item) => item.tool_name === selectedName) ?? null;
  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return catalog?.tools ?? [];
    return (catalog?.tools ?? []).filter((item) => `${item.display_name} ${item.tool_name} ${item.category}`.toLowerCase().includes(keyword));
  }, [catalog, query]);

  function mergeTool(tool: McpTool) {
    setCatalog((current) => current ? {
      ...current,
      tools: current.tools.map((item) => item.tool_name === tool.tool_name ? tool : item),
      enabled_count: current.tools.reduce((count, item) => count + (item.tool_name === tool.tool_name ? Number(tool.is_enabled) : Number(item.is_enabled)), 0),
      planner_count: current.tools.reduce((count, item) => count + (item.tool_name === tool.tool_name ? Number(tool.is_enabled && tool.planner_enabled) : Number(item.is_enabled && item.planner_enabled)), 0),
    } : current);
    if (tool.tool_name === selectedName) {
      setDraft({
        display_name: tool.display_name,
        description: tool.description,
        timeout_seconds: tool.timeout_seconds,
        max_rows: tool.max_rows,
        operator_note: tool.operator_note ?? "",
      });
    }
  }

  function selectTool(tool: McpTool) {
    setSelectedName(tool.tool_name);
    setDraft({
      display_name: tool.display_name,
      description: tool.description,
      timeout_seconds: tool.timeout_seconds,
      max_rows: tool.max_rows,
      operator_note: tool.operator_note ?? "",
    });
  }

  async function updateTool(toolName: string, values: Parameters<typeof productionServices.adminMcp.update>[1], action: string) {
    if (busy) return;
    setBusy(action);
    setError("");
    setNotice("");
    try {
      mergeTool(await productionServices.adminMcp.update(toolName, values));
      setNotice("MCP 工具配置已生效。后续规划会立即遵循这项边界。");
    } catch (updateError) {
      setError(humanizeApiError(updateError));
    } finally {
      setBusy("");
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await updateTool(selected.tool_name, {
      display_name: draft.display_name.trim(),
      description: draft.description.trim(),
      timeout_seconds: draft.timeout_seconds,
      max_rows: draft.max_rows,
      operator_note: draft.operator_note.trim() || null,
    }, "save");
  }

  async function validate() {
    if (!selected || busy) return;
    setBusy("validate");
    setError("");
    setNotice("");
    try {
      const result = await productionServices.adminMcp.validate(selected.tool_name);
      mergeTool(result.tool);
      setNotice(result.ready ? "校验通过：工具配置与所需数据域均已就绪。" : result.issues.join("；"));
    } catch (validationError) {
      setError(humanizeApiError(validationError));
    } finally {
      setBusy("");
    }
  }

  function toggleComponent(toolName: string) {
    setCreateDraft((current) => {
      const selected = current.component_tools.includes(toolName);
      if (!selected && current.component_tools.length >= 4) return current;
      return {
        ...current,
        component_tools: selected
          ? current.component_tools.filter((name) => name !== toolName)
          : [...current.component_tools, toolName],
      };
    });
  }

  async function createCompositeTool(event: FormEvent) {
    event.preventDefault();
    if (busy || createDraft.component_tools.length === 0) return;
    setBusy("create");
    setError("");
    setNotice("");
    try {
      const created = await productionServices.adminMcp.create({
        tool_name: createDraft.tool_name.trim(),
        display_name: createDraft.display_name.trim(),
        description: createDraft.description.trim(),
        category: createDraft.category.trim(),
        component_tools: createDraft.component_tools,
        operator_note: createDraft.operator_note.trim() || undefined,
      });
      await loadCatalog(created.tool_name);
      setCreateOpen(false);
      setCreateDraft({ tool_name: "custom_", display_name: "", description: "", category: "综合经营", component_tools: [], operator_note: "" });
      setNotice("组合工具已创建并保持停用。完成就绪度校验后再启用执行与自动规划。");
    } catch (createError) {
      setError(humanizeApiError(createError));
    } finally {
      setBusy("");
    }
  }

  const builtInTools = catalog?.tools.filter((tool) => tool.source_type === "built_in") ?? [];

  return (
    <main className="production-admin-main mcp-admin-main">
      <header className="production-admin-heading">
        <div><p>执行能力</p><h1>MCP 工具注册表</h1><span>只开放经过审计的经营工具；查询规划、意图路由和后续 Skill 共用同一配置。</span></div>
        <div className="production-admin-heading-actions"><span className="production-admin-status positive"><i aria-hidden="true" />{catalog ? `${catalog.enabled_count} / ${catalog.tools.length} 已启用` : "正在读取"}</span><button className="primary-button" type="button" onClick={() => { setError(""); setNotice(""); setCreateOpen(true); }}>新增工具</button></div>
      </header>
      <section className="mcp-boundary-note"><strong>受控边界</strong><span>可以新增由 1–4 个系统工具组成的企业组合工具；仍不接受任意 SQL、脚本或外部地址。</span></section>
      <div className="mcp-registry-layout">
        <section className="mcp-tool-index" aria-label="MCP 工具列表">
          <header><div><strong>工具</strong><small>{catalog ? `${catalog.planner_count} 个可被规划器选择` : "加载中"}</small></div><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索工具" aria-label="搜索 MCP 工具" /></header>
          <div>{filtered.map((tool) => <article className={selectedName === tool.tool_name ? "selected" : ""} key={tool.tool_name}><button type="button" onClick={() => selectTool(tool)}><span><strong>{tool.display_name}</strong><small>{tool.tool_name}</small><em>{tool.source_type === "composite" ? "企业组合" : "系统内置"}</em></span><i className={`mcp-readiness ${tool.readiness}`} title={tool.readiness_issues.join("；")} aria-label={tool.readiness} /></button><label className="switch mcp-inline-switch" title="启用工具"><input type="checkbox" checked={tool.is_enabled} disabled={Boolean(busy)} onChange={(event) => void updateTool(tool.tool_name, { is_enabled: event.target.checked }, `enable:${tool.tool_name}`)} /><span aria-hidden="true" /></label></article>)}</div>
          {!filtered.length && <p className="mcp-empty">没有匹配的工具。</p>}
        </section>
        <section className="mcp-tool-detail" aria-live="polite">
          {!selected ? <div className="anspire-loading">请选择一个 MCP 工具。</div> : <form onSubmit={save}>
            <header><div><small>{selected.category} · {selected.source_type === "composite" ? "企业组合" : "系统内置"}</small><h2>{selected.display_name}</h2><code>{selected.tool_name} · v{selected.definition_version}</code></div><span className={`mcp-detail-status ${selected.readiness}`}>{selected.readiness === "ready" ? "可运行" : selected.readiness === "disabled" ? "已停用" : "数据未就绪"}</span></header>
            <div className="mcp-tool-controls"><label><span>允许执行</span><span className="switch"><input type="checkbox" checked={selected.is_enabled} disabled={Boolean(busy)} onChange={(event) => void updateTool(selected.tool_name, { is_enabled: event.target.checked }, "enable")} /><span aria-hidden="true" /></span><small>关闭后，MCP Hub 会直接拒绝调用。</small></label><label><span>允许自动规划</span><span className="switch"><input type="checkbox" checked={selected.planner_enabled} disabled={Boolean(busy) || !selected.is_enabled} onChange={(event) => void updateTool(selected.tool_name, { planner_enabled: event.target.checked }, "planner")} /><span aria-hidden="true" /></span><small>关闭后仍可保留工具，但 Harness 不会自动选择。</small></label></div>
            <div className="mcp-tool-form"><label><span>显示名称</span><input value={draft.display_name} maxLength={160} onChange={(event) => setDraft((current) => ({ ...current, display_name: event.target.value }))} /></label><label className="wide"><span>用途说明</span><textarea rows={3} value={draft.description} maxLength={2000} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} /></label><label><span>超时（秒）</span><input type="number" min={3} max={60} value={draft.timeout_seconds} onChange={(event) => setDraft((current) => ({ ...current, timeout_seconds: Number(event.target.value) }))} /></label><label><span>最大返回行数</span><input type="number" min={1} max={100} value={draft.max_rows} onChange={(event) => setDraft((current) => ({ ...current, max_rows: Number(event.target.value) }))} /></label><label className="wide"><span>运维备注</span><textarea rows={2} value={draft.operator_note} maxLength={500} onChange={(event) => setDraft((current) => ({ ...current, operator_note: event.target.value }))} placeholder="仅管理端可见" /></label></div>
            <section className="mcp-schema"><header><strong>规划器可用参数</strong><small>{selected.domains.length ? `依赖数据域：${selected.domains.join("、")}` : "不依赖经营事实"}</small></header><div>{Object.entries(selected.parameters).map(([name, schema]) => <span key={name}><code>{name}</code><small>{String(schema.description ?? schema.type ?? "参数")}</small></span>)}{!Object.keys(selected.parameters).length && <p>该工具不接受可变业务参数，查询范围由权限令牌注入。</p>}</div></section>
            {selected.source_type === "composite" && <section className="mcp-composition"><header><strong>组合执行</strong><small>按依赖工具各自的权限与返回边界执行</small></header><div>{selected.component_tools.map((name, index) => <span key={name}><i>{String(index + 1).padStart(2, "0")}</i><strong>{catalog?.tools.find((tool) => tool.tool_name === name)?.display_name ?? name}</strong><code>{name}</code></span>)}</div></section>}
            {selected.readiness_issues.length > 0 && <p className="anspire-error" role="alert">{selected.readiness_issues.join("；")}</p>}
            {error && <p className="anspire-error" role="alert">{error}</p>}
            {notice && <p className="anspire-notice" role="status">{notice}</p>}
            <footer><span>配置变更会写入审计日志，并由规划器和 MCP Hub 同时执行。</span><div><button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={() => void validate()}>{busy === "validate" ? "正在校验…" : "校验就绪度"}</button><button className="primary-button" type="submit" disabled={Boolean(busy) || !draft.display_name.trim() || !draft.description.trim()}>{busy === "save" ? "正在保存…" : "保存配置"}</button></div></footer>
          </form>}
        </section>
      </div>
      {createOpen && <div className="mcp-create-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setCreateOpen(false); }}><section className="mcp-create-dialog" role="dialog" aria-modal="true" aria-labelledby="mcp-create-title"><header><div><small>企业组合工具</small><h2 id="mcp-create-title">新增 MCP 工具</h2><p>组合已有的受审查询能力，不创建新的 SQL 或外部连接。</p></div><button type="button" disabled={Boolean(busy)} onClick={() => setCreateOpen(false)} aria-label="关闭">×</button></header><form onSubmit={createCompositeTool}><div className="mcp-create-grid"><label><span>工具名称</span><input value={createDraft.display_name} maxLength={160} autoFocus onChange={(event) => setCreateDraft((current) => ({ ...current, display_name: event.target.value }))} placeholder="例如：重点客户风险体检" /></label><label><span>工具标识</span><input value={createDraft.tool_name} maxLength={64} spellCheck={false} onChange={(event) => setCreateDraft((current) => ({ ...current, tool_name: event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "" ) }))} /><small>必须以 custom_ 开头，发布后不可修改。</small></label><label><span>业务分类</span><input value={createDraft.category} maxLength={80} onChange={(event) => setCreateDraft((current) => ({ ...current, category: event.target.value }))} /></label><label className="wide"><span>用途说明</span><textarea rows={3} value={createDraft.description} maxLength={2000} onChange={(event) => setCreateDraft((current) => ({ ...current, description: event.target.value }))} placeholder="说明规划器何时应使用这个工具，以及它能够回答什么问题。" /></label></div><fieldset className="mcp-component-picker"><legend>选择组成工具 <small>{createDraft.component_tools.length} / 4</small></legend><p>执行时会自动合并共同参数、数据时间和数字证据。</p><div>{builtInTools.map((tool) => { const checked = createDraft.component_tools.includes(tool.tool_name); return <label className={checked ? "selected" : ""} key={tool.tool_name}><input type="checkbox" checked={checked} disabled={!checked && createDraft.component_tools.length >= 4} onChange={() => toggleComponent(tool.tool_name)} /><span><strong>{tool.display_name}</strong><small>{tool.category} · {tool.domains.join("、") || "权限范围"}</small></span><i aria-hidden="true">{checked ? "✓" : "+"}</i></label>; })}</div></fieldset><label className="mcp-create-note"><span>运维备注</span><textarea rows={2} value={createDraft.operator_note} maxLength={500} onChange={(event) => setCreateDraft((current) => ({ ...current, operator_note: event.target.value }))} placeholder="仅管理员可见，可留空" /></label>{error && <p className="anspire-error" role="alert">{error}</p>}<footer><p>创建后默认停用。请先校验依赖工具和数据域，再手动启用。</p><div><button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={() => setCreateOpen(false)}>取消</button><button className="primary-button" type="submit" disabled={Boolean(busy) || !createDraft.tool_name.match(/^custom_[a-z0-9_]+$/) || !createDraft.display_name.trim() || createDraft.description.trim().length < 12 || !createDraft.category.trim() || createDraft.component_tools.length === 0}>{busy === "create" ? "正在创建…" : "创建工具"}</button></div></footer></form></section></div>}
    </main>
  );
}
