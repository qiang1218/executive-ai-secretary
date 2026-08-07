"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { humanizeApiError } from "./api-client";
import { productionServices } from "./services";
import type {
  AdminModelAuthorization,
  AdminModelCatalog,
  McpSchemaCandidate,
  McpSchemaCatalog,
  McpSchemaDeleteOut,
  McpSchemaRecord,
  McpSchemaRegisterIn,
  McpSchemaUpdate,
  McpSchemaRefreshOut,
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
  const [toast, setToast] = useState<{ message: string; tone: "success" | "failed" | "info" } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);

  const showToast = (message: string, tone: "success" | "failed" | "info" = "success") => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ message, tone });
    toastTimer.current = setTimeout(() => setToast(null), 1000);
  };

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
      showToast(
        `${model.display_name} · 通过 ${result.latency_ms ?? "—"} ms`,
        "success",
      );
    } catch (testError) {
      const message = humanizeApiError(testError);
      setError(message);
      showToast(`${model.display_name} · ${message}`, "failed");
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
  const visibleModels = useMemo(
    () =>
      (catalog?.models ?? [])
        .filter((model) => model.selectable)
        .filter((model) =>
          modelView === "all"
            ? true
            : modelView === "authorized"
              ? model.is_authorized
              : !model.is_authorized,
        )
        .filter((model) => {
          const query = modelSearch.trim().toLocaleLowerCase("zh-CN");
          if (!query) return true;
          return [model.display_name, model.name, model.family, model.model_id].some(
            (value) => value.toLocaleLowerCase("zh-CN").includes(query),
          );
        }),
    [catalog, modelView, modelSearch],
  );

  // 按 family 聚合同系列模型(GPT/GLM/Claude … 同 column 排布)
  const groupedModels = useMemo(() => {
    const buckets = new Map<string, AdminModelAuthorization[]>();
    for (const model of visibleModels) {
      const key = model.family || "未分类";
      const list = buckets.get(key);
      if (list) list.push(model);
      else buckets.set(key, [model]);
    }
    // 稳定顺序:GPT → GLM → Claude → … → 未分类,其余按字典序
    const order = (family: string): number => {
      const index = ["GPT", "GLM", "Claude"].indexOf(family);
      return index === -1 ? 1000 + Array.from(buckets.keys()).indexOf(family) : index;
    };
    return Array.from(buckets.entries())
      .sort(([a], [b]) => {
        const diff = order(a) - order(b);
        return diff !== 0 ? diff : a.localeCompare(b, "zh-CN");
      })
      .map(([family, items]) => ({ family, items }));
  }, [visibleModels]);

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
        {!catalog ? <div className="anspire-loading">正在读取模型授权目录…</div> : <div className="admin-model-list">{groupedModels.map((group) => (
          <section key={group.family} className="admin-model-group">
            <header className="admin-model-group-title">
              <h4>{group.family}</h4>
              <small>{group.items.length} 个模型</small>
            </header>
            <div className="admin-model-grid">
              {group.items.map((model) => {
                const testCurrent = model.test_status === "success" && model.tested_credential_version === model.current_credential_version;
                return (
                  <article key={model.model_id} className={model.is_authorized ? "authorized" : ""}>
                    <div className="admin-model-identity">
                      <span className={`model-test-dot ${testCurrent ? "success" : model.test_status}`} aria-hidden="true" />
                      <span className="admin-model-tag">{model.display_name}</span>
                    </div>
                    <p>{model.profile}</p>
                    <div className="admin-model-state">
                      {model.is_default && <b>默认</b>}
                      {model.is_authorized && !model.is_default && (
                        <button type="button" disabled={Boolean(busy)} onClick={() => void setDefault(model)}>
                          {busy === `default:${model.model_id}` ? "设置中…" : "默认"}
                        </button>
                      )}
                    </div>
                    <div className="admin-model-actions">
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={Boolean(busy) || !config?.is_configured}
                        onClick={() => void testModel(model)}
                      >
                        {busy === `test:${model.model_id}` ? "测试中…" : testCurrent ? "重测" : "测试"}
                      </button>
                      <button
                        className={model.is_authorized ? "secondary-button" : "primary-button"}
                        type="button"
                        disabled={Boolean(busy) || (!model.is_authorized && !testCurrent)}
                        onClick={() => void toggleAuthorization(model)}
                      >
                        {busy === `authorize:${model.model_id}` ? "更新中…" : model.is_authorized ? "撤销" : "授权"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))}{!visibleModels.length && <p className="data-operations-empty">没有符合当前筛选条件的模型。</p>}</div>}
      </section>
      {toast && (
        <output className={`admin-toast ${toast.tone}`} aria-live="polite">
          {toast.message}
        </output>
      )}
    </main>
  );
}
// ══════════════════════════════════════════════════════════
// MCP v2 Schema 管理面板
// ══════════════════════════════════════════════════════════

export function McpSchemaPanel() {
  const [catalog, setCatalog] = useState<McpSchemaCatalog | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | false>(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [candidates, setCandidates] = useState<McpSchemaCandidate[]>([]);
  const [expanded, setExpanded] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    productionServices.adminMcpSchema.list()
      .then((data) => { if (!cancelled) setCatalog(data); })
      .catch((err) => { if (!cancelled) setError(humanizeApiError(err)); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await productionServices.adminMcpSchema.listCandidates();
        if (!cancelled) setCandidates(data.candidates);
      } catch {
        // 候选加载失败不影响主列表,直接吞掉。
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!expanded || !catalog) return;
    // 用户主动展开候选面板时强制再拉一次(可能刚注册了表)。
    let cancelled = false;
    (async () => {
      try {
        const data = await productionServices.adminMcpSchema.listCandidates();
        if (!cancelled) setCandidates(data.candidates);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [expanded, catalog]);

  const filtered = useMemo(() => {
    if (!catalog) return [];
    const q = query.trim().toLowerCase();
    if (!q) return catalog.tables;
    return catalog.tables.filter(
      (t) =>
        t.table_name.toLowerCase().includes(q) ||
        t.display_name.toLowerCase().includes(q) ||
        t.category.toLowerCase().includes(q),
    );
  }, [catalog, query]);

  const selected = useMemo(() => {
    if (!selectedTable || !catalog) return null;
    return catalog.tables.find((t) => t.table_name === selectedTable) ?? null;
  }, [selectedTable, catalog]);

  async function updateTable(tableName: string, values: McpSchemaUpdate) {
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const updated = await productionServices.adminMcpSchema.update(tableName, values);
      setCatalog((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          tables: prev.tables.map((t) =>
            t.table_name === tableName ? { ...t, ...updated } : t,
          ),
        };
      });
      setNotice("保存成功");
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function refreshTable(tableName: string) {
    setBusy("refresh");
    setError("");
    setNotice("");
    try {
      const result = await productionServices.adminMcpSchema.refresh(tableName);
      if (result.error) {
        setError(`刷新失败：${result.error}`);
      } else {
        setNotice(`刷新成功，发现 ${result.columns_discovered} 列（v${result.schema_version}）`);
        // 重新加载 catalog
        const data = await productionServices.adminMcpSchema.list();
        setCatalog(data);
      }
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function refreshAll() {
    setBusy("refreshAll");
    setError("");
    setNotice("");
    try {
      const data = await productionServices.adminMcpSchema.refreshAll();
      setCatalog(data);
      setNotice(`刷新完成，共 ${data.total} 张表`);
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function registerCandidate(tableName: string) {
    setBusy(`register:${tableName}`);
    setError("");
    setNotice("");
    try {
      await productionServices.adminMcpSchema.register(tableName, { is_enabled: true });
      // 重新拉列表(已注册表与候选都会更新)
      const [catalogData, candData] = await Promise.all([
        productionServices.adminMcpSchema.list(),
        productionServices.adminMcpSchema.listCandidates(),
      ]);
      setCatalog(catalogData);
      setCandidates(candData.candidates);
      setSelectedTable(tableName);
      setNotice(`已注册 ${tableName}`);
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function unregisterTable(tableName: string) {
    if (!window.confirm(`注销 ${tableName}？注销后 Agent 不能再查询此表。`)) return;
    setBusy(`unregister:${tableName}`);
    setError("");
    setNotice("");
    try {
      const result: McpSchemaDeleteOut = await productionServices.adminMcpSchema.unregister(tableName);
      const [catalogData, candData] = await Promise.all([
        productionServices.adminMcpSchema.list(),
        productionServices.adminMcpSchema.listCandidates(),
      ]);
      setCatalog(catalogData);
      setCandidates(candData.candidates);
      if (selectedTable === tableName) setSelectedTable(null);
      setNotice(result.message);
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  const categoryLabel: Record<string, string> = {
    opportunity: "商机",
    delivery: "交付",
    collection: "回款",
    target: "目标",
    dimension: "维度",
    snapshot: "快照",
  };

  return (
    <main className="production-admin-main mcp-admin-main">
      <header className="production-admin-heading">
        <div>
          <p>数据 Schema</p>
          <h1>MCP 表结构注册</h1>
          <span>Agent 通过 discover → query → execute 三步自动查询数据表。</span>
        </div>
        <div className="production-admin-heading-actions">
          <span className="production-admin-status positive">
            <i aria-hidden="true" />
            {catalog ? `${catalog.enabled_count} / ${catalog.total} 已启用` : "正在读取"}
          </span>
          <button
            className="primary-button"
            type="button"
            disabled={busy === "refreshAll"}
            onClick={() => void refreshAll()}
          >
            {busy === "refreshAll" ? "正在刷新…" : "刷新所有 Schema"}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            {expanded ? "折叠候选表" : `展开候选表${candidates.length ? ` (${candidates.length})` : ""}`}
          </button>
        </div>
      </header>

      <div className="mcp-registry-layout">
        {/* ── 左侧：表列表 ── */}
        <section className="mcp-tool-index" aria-label="数据表列表">
          <header>
            <div>
              <strong>数据表</strong>
              <small>{catalog ? `${catalog.total} 张表` : "加载中"}</small>
            </div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索表名或分类"
              aria-label="搜索数据表"
            />
          </header>
          <div>
            {filtered.map((t) => (
              <article
                className={selectedTable === t.table_name ? "selected" : ""}
                key={t.table_name}
              >
                <button type="button" onClick={() => setSelectedTable(t.table_name)}>
                  <span>
                    <strong>{t.display_name}</strong>
                    <small>{t.table_name}</small>
                    <em>{categoryLabel[t.category] ?? t.category}</em>
                  </span>
                  <i
                    className={`mcp-readiness ${t.is_enabled ? "ready" : "disabled"}`}
                    title={t.is_enabled ? "已启用" : "已停用"}
                    aria-label={t.is_enabled ? "ready" : "disabled"}
                  />
                </button>
                <label className="switch mcp-inline-switch" title="启用此表">
                  <input
                    type="checkbox"
                    checked={t.is_enabled}
                    disabled={Boolean(busy)}
                    onChange={(e) =>
                      void updateTable(t.table_name, { is_enabled: e.target.checked })
                    }
                  />
                  <span aria-hidden="true" />
                </label>
              </article>
            ))}
          </div>
          {!filtered.length && <p className="mcp-empty">没有匹配的表。</p>}
          {expanded && (
            <div className="mcp-candidate-section">
              <header>
                <strong>候选物理表</strong>
                <small>
                  {candidates.length
                    ? `${candidates.length} 张未注册`
                    : "全部内置表都已注册"}
                </small>
              </header>
              {candidates.length === 0 ? (
                <p className="mcp-empty">暂时没有未注册的物理表。</p>
              ) : (
                candidates.map((c) => (
                  <article key={c.table_name}>
                    <button
                      type="button"
                      onClick={() => void registerCandidate(c.table_name)}
                      disabled={Boolean(busy) && busy !== `register:${c.table_name}`}
                    >
                      <span>
                        <strong>{c.display_name}</strong>
                        <small>{c.table_name}</small>
                        <em>{categoryLabel[c.category] ?? c.category}</em>
                        <p>{c.description}</p>
                      </span>
                      <i
                        className="mcp-readiness disabled"
                        title="未注册"
                        aria-label="candidate"
                      />
                    </button>
                  </article>
                ))
              )}
            </div>
          )}
        </section>

        {/* ── 右侧：表详情 ── */}
        <section className="mcp-tool-detail" aria-live="polite">
          {!selected ? (
            <div className="anspire-loading">请选择一张数据表查看详情。</div>
          ) : (
            <>
              <header>
                <div>
                  <small>
                    {categoryLabel[selected.category] ?? selected.category}
                    {selected.schema_version > 0 ? ` · v${selected.schema_version}` : ""}
                  </small>
                  <h2>{selected.display_name}</h2>
                  <code>{selected.table_name}</code>
                </div>
                <span
                  className={`mcp-detail-status ${selected.is_enabled ? "ready" : "disabled"}`}
                >
                  {selected.is_enabled ? "已启用" : "已停用"}
                </span>
              </header>

              <div className="mcp-tool-controls">
                <label>
                  <span>Agent 可见</span>
                  <span className="switch">
                    <input
                      type="checkbox"
                      checked={selected.is_enabled}
                      disabled={Boolean(busy)}
                      onChange={(e) =>
                        void updateTable(selected.table_name, { is_enabled: e.target.checked })
                      }
                    />
                    <span aria-hidden="true" />
                  </span>
                  <small>停用后 Agent 无法发现或查询此表。</small>
                </label>
              </div>

              <div className="mcp-tool-form">
                <label>
                  <span>用途说明</span>
                  <textarea
                    rows={3}
                    value={selected.description}
                    maxLength={2000}
                    readOnly
                  />
                </label>
                <label>
                  <span>最大返回行数</span>
                  <input
                    type="number"
                    min={1}
                    max={1000}
                    value={selected.max_rows}
                    disabled={Boolean(busy)}
                    onChange={(e) =>
                      void updateTable(selected.table_name, {
                        max_rows: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  <span>查询超时（秒）</span>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={selected.query_timeout_seconds}
                    disabled={Boolean(busy)}
                    onChange={(e) =>
                      void updateTable(selected.table_name, {
                        query_timeout_seconds: Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>

              {/* 列结构 */}
              <section className="mcp-schema">
                <header>
                  <strong>列结构</strong>
                  <small>
                    {selected.column_schema.length > 0
                      ? `${selected.column_schema.length} 列`
                      : "未刷新"}
                  </small>
                </header>
                <div>
                  {selected.column_schema.length === 0 ? (
                    <p>尚未刷新 Schema，点击下方按钮从数据库自动发现列结构。</p>
                  ) : (
                    selected.column_schema.map((col) => (
                      <span key={col.name}>
                        <code>
                          {col.name}
                          {col.is_primary_key ? " PK" : ""}
                        </code>
                        <small>
                          {col.type}
                          {!col.nullable ? " NOT NULL" : ""}
                          {col.references
                            ? ` → ${col.references.table}.${col.references.column}`
                            : ""}
                          {col.comment ? ` - ${col.comment}` : ""}
                        </small>
                      </span>
                    ))
                  )}
                </div>
              </section>

              {/* 示例数据 */}
              {selected.sample_rows && selected.sample_rows.length > 0 && (
                <section className="mcp-schema">
                  <header>
                    <strong>示例数据</strong>
                    <small>前 {selected.sample_rows.length} 行</small>
                  </header>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse" }}>
                      <thead>
                        <tr>
                          {Object.keys(selected.sample_rows[0]).slice(0, 6).map((k) => (
                            <th
                              key={k}
                              style={{
                                padding: "4px 8px",
                                textAlign: "left",
                                borderBottom: "1px solid var(--border)",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {k}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {selected.sample_rows.map((row, i) => (
                          <tr key={i}>
                            {Object.values(row)
                              .slice(0, 6)
                              .map((v, j) => (
                                <td
                                  key={j}
                                  style={{
                                    padding: "4px 8px",
                                    borderBottom: "1px solid var(--border-subtle)",
                                    maxWidth: "200px",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {String(v ?? "NULL")}
                                </td>
                              ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {selected.last_refreshed_at && (
                <p className="anspire-notice" role="status">
                  Schema 最后刷新：{new Date(selected.last_refreshed_at).toLocaleString("zh-CN")}
                </p>
              )}
              {error && <p className="anspire-error" role="alert">{error}</p>}
              {notice && <p className="anspire-notice" role="status">{notice}</p>}

              <footer>
                <span>刷新会从数据库自动发现最新列结构和示例数据。</span>
                <div>
                  <button
                    className="danger-button"
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={() => void unregisterTable(selected.table_name)}
                  >
                    {busy === `unregister:${selected.table_name}` ? "注销中…" : "注销"}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busy === "refresh"}
                    onClick={() => void refreshTable(selected.table_name)}
                  >
                    {busy === "refresh" ? "正在刷新…" : "刷新 Schema"}
                  </button>
                </div>
              </footer>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
