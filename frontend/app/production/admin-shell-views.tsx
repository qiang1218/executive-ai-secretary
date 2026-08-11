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
  EmbeddingConfigOut,
  EmbeddingStatsOut,
  ModelProviderConfig,
  Skill,
  SkillCreate,
  SkillListItem,
  SkillListOut,
  SkillUpdate,
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

const EMBEDDING_STATUS_LABEL: Record<string, string> = {
  idle: "未构建",
  running: "构建中",
  succeeded: "成功",
  failed: "失败",
  partial_success: "部分成功",
};

function EmbeddingSection({ tableName, columns }: { tableName: string; columns: { name: string; type: string }[] }) {
  const [config, setConfig] = useState<EmbeddingConfigOut | null>(null);
  const [stats, setStats] = useState<EmbeddingStatsOut | null>(null);
  const [contentFields, setContentFields] = useState<string>("");
  const [metadataFields, setMetadataFields] = useState<string>("");
  const [busy, setBusy] = useState<string | false>(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadAll() {
    try {
      const [cfg, st] = await Promise.all([
        productionServices.adminMcpSchema.getEmbeddingConfig(tableName),
        productionServices.adminMcpSchema.getEmbeddingStats(tableName),
      ]);
      setConfig(cfg);
      setStats(st);
      setContentFields((cfg.embedding_config_json?.content_fields ?? []).join(", "));
      setMetadataFields((cfg.embedding_config_json?.metadata_fields ?? []).join(", "));
    } catch (err) {
      setError(humanizeApiError(err));
    }
  }

  useEffect(() => {
    setError("");
    setNotice("");
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableName]);

  // 当 config 状态变化时（如触发后变 running），轮询
  useEffect(() => {
    if (!config || config.embedding_status !== "running") return;
    const timer = setInterval(() => { void loadAll(); }, 3000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config?.embedding_status]);

  async function saveConfig() {
    setBusy("save");
    setError("");
    setNotice("");
    const cf = contentFields.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
    const mf = metadataFields.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
    if (cf.length === 0) {
      setError("content_fields 至少填一个字段");
      setBusy(false);
      return;
    }
    try {
      const cfg = await productionServices.adminMcpSchema.configureEmbedding(tableName, {
        content_fields: cf,
        metadata_fields: mf,
      });
      setConfig(cfg);
      setNotice("配置已保存");
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function triggerIndex() {
    setBusy("trigger");
    setError("");
    setNotice("");
    try {
      // 前端预检：必须先保存 content_fields 才能触发向量化，
      // 否则后端会返回 embedding_not_configured。
      const contentFields = (config?.embedding_config_json?.content_fields ?? []).filter((f) => f.trim().length > 0);
      if (contentFields.length === 0) {
        setError("请先在上方填写 content_fields 并点击「保存配置」，再触发向量化。");
        return;
      }
      const result = await productionServices.adminMcpSchema.triggerEmbedding(tableName);
      setNotice(`已触发构建，Job ID: ${result.job_id}`);
      // 立即刷新一次状态
      await loadAll();
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  const status = config?.embedding_status ?? "idle";
  const statusLabel = EMBEDDING_STATUS_LABEL[status] ?? status;
  const summary = config?.embedding_summary_json ?? {};
  const lastIndexed = config?.last_indexed_at
    ? new Date(config.last_indexed_at).toLocaleString("zh-CN")
    : null;

  return (
    <section className="mcp-schema mcp-embedding-section">
      <header>
        <strong>向量索引</strong>
        <small>
          状态：<span className={`mcp-embedding-status ${status}`}>{statusLabel}</span>
          {lastIndexed && <span> · 上次构建：{lastIndexed}</span>}
        </small>
      </header>

      <div className="mcp-embedding-stats">
        <span><em>总行数</em><strong>{stats?.total ?? 0}</strong></span>
        <span><em>已索引</em><strong className="mcp-embedding-stat-ok">{stats?.indexed ?? 0}</strong></span>
        <span><em>失败</em><strong className="mcp-embedding-stat-err">{stats?.failed ?? 0}</strong></span>
        <span><em>待处理</em><strong>{stats?.pending ?? 0}</strong></span>
      </div>

      {status === "running" && (
        <p className="anspire-notice" role="status">
          正在构建向量索引，请稍候（页面会自动刷新）…
        </p>
      )}
      {status !== "idle" && status !== "running" && (
        <div className="mcp-embedding-summary">
          <small>上次构建摘要</small>
          <code>{JSON.stringify(summary, null, 2)}</code>
        </div>
      )}

      <div className="mcp-tool-form">
        <label className="wide">
          <span>content_fields（拼接成 embedding 内容的字段，逗号分隔）</span>
          <textarea
            rows={2}
            value={contentFields}
            onChange={(e) => setContentFields(e.target.value)}
            placeholder="title, customer_name, opportunity_code, sales_owner"
            disabled={busy === "save" || status === "running"}
          />
        </label>
        <label className="wide">
          <span>metadata_fields（冗余到 metadata 用于过滤的字段，逗号分隔，可选）</span>
          <textarea
            rows={2}
            value={metadataFields}
            onChange={(e) => setMetadataFields(e.target.value)}
            placeholder="industry, status_code, customer_value_level"
            disabled={busy === "save" || status === "running"}
          />
        </label>
      </div>

      {columns.length > 0 && (
        <div className="mcp-embedding-cols">
          <small>可用字段（点击复制到 content_fields）：</small>
          <div className="mcp-embedding-col-chips">
            {columns.map((c) => (
              <button
                key={c.name}
                type="button"
                className="mcp-col-chip"
                onClick={() => {
                  const cur = contentFields.split(/[,\s]+/).filter(Boolean);
                  if (!cur.includes(c.name)) {
                    setContentFields([...cur, c.name].join(", "));
                  }
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="anspire-error" role="alert">{error}</p>}
      {notice && <p className="anspire-notice" role="status">{notice}</p>}

      <footer className="mcp-embedding-footer">
        <button
          className="secondary-button"
          type="button"
          disabled={busy === "save" || status === "running"}
          onClick={() => void saveConfig()}
        >
          {busy === "save" ? "保存中…" : "保存配置"}
        </button>
        <button
          className="primary-button"
          type="button"
          disabled={busy === "trigger" || status === "running"}
          onClick={() => void triggerIndex()}
          title="保存配置后才能触发"
        >
          {busy === "trigger" ? "触发中…" : status === "running" ? "构建中…" : "触发向量化"}
        </button>
      </footer>
    </section>
  );
}

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
            <form onSubmit={(e) => e.preventDefault()}>
              <div className="accent-strip" aria-hidden="true" />

              <header>
                <div>
                  <small>
                    {categoryLabel[selected.category] ?? selected.category}
                    {selected.schema_version > 0 ? ` · v${selected.schema_version}` : ""}
                  </small>
                  <h2>{selected.display_name}</h2>
                  <code>{selected.table_name}</code>
                </div>
                <span className={`mcp-detail-status ${selected.is_enabled ? "ready" : "disabled"}`}>
                  <i aria-hidden="true" />
                  {selected.is_enabled ? "已启用" : "已停用"}
                </span>
              </header>

              <div className="mcp-detail-meta">
                <span className="mcp-detail-meta-chip">
                  <em>列</em>
                  <strong>{selected.column_schema.length}</strong>
                </span>
                <span className="mcp-detail-meta-chip">
                  <em>限行</em>
                  <strong>{selected.max_rows}</strong>
                </span>
                <span className="mcp-detail-meta-chip">
                  <em>超时</em>
                  <strong>{selected.query_timeout_seconds}s</strong>
                </span>
                {selected.sample_rows && selected.sample_rows.length > 0 && (
                  <span className="mcp-detail-meta-chip">
                    <em>示例</em>
                    <strong>{selected.sample_rows.length} 行</strong>
                  </span>
                )}
              </div>

              <div className="mcp-tool-controls">
                <label className="mcp-switch-card">
                  <span>Agent 可见</span>
                  <span className={`mcp-switch-card-state ${selected.is_enabled ? "on" : ""}`}>
                    {selected.is_enabled ? "ON" : "OFF"}
                  </span>
                  <span className="switch">
                    <input
                      type="checkbox"
                      checked={selected.is_enabled}
                      disabled={Boolean(busy)}
                      onChange={(e) =>
                        void updateTable(selected.table_name, {
                          is_enabled: e.target.checked,
                        })
                      }
                    />
                    <span aria-hidden="true" />
                  </span>
                  <small>停用后 Agent 无法发现或查询此表。</small>
                </label>
              </div>

              <div className="mcp-tool-form">
                <label className="wide">
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
                {selected.column_schema.length === 0 ? (
                  <p>尚未刷新 Schema，点击下方按钮从数据库自动发现列结构。</p>
                ) : (
                  <div className="mcp-column-grid">
                    {selected.column_schema.map((col) => (
                      <article key={col.name} className="mcp-column-row">
                        <span className="col-name">
                          {col.name}
                          {col.is_primary_key && <span className="pk">PK</span>}
                        </span>
                        <span className="col-meta">
                          {col.references && (
                            <span>FK → {col.references.table}.{col.references.column}</span>
                          )}
                          {col.comment && <span>- {col.comment}</span>}
                          {!col.nullable && <em>NOT NULL</em>}
                        </span>
                        <span className="col-type">{col.type}</span>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              {/* 向量索引 */}
              <EmbeddingSection
                tableName={selected.table_name}
                columns={selected.column_schema.map((c) => ({ name: c.name, type: c.type }))}
              />

              {/* 示例数据 */}
              {selected.sample_rows && selected.sample_rows.length > 0 && (
                <section className="mcp-schema mcp-schema-sample">
                  <header>
                    <strong>示例数据</strong>
                    <small>前 {selected.sample_rows.length} 行</small>
                  </header>
                  <div className="mcp-sample-wrap">
                    <table className="mcp-sample-table">
                      <thead>
                        <tr>
                          {Object.keys(selected.sample_rows[0])
                            .slice(0, 6)
                            .map((k) => (
                              <th key={k}>{k}</th>
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
                                  className={v == null ? "cell-null" : undefined}
                                >
                                  {v == null ? "NULL" : String(v)}
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
                  Schema 最后刷新：
                  {new Date(selected.last_refreshed_at).toLocaleString("zh-CN")}
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
            </form>
          )}
        </section>
      </div>
    </main>
  );
}

// ====================== Skills ======================

type SkillEditMode =
  | { kind: "closed" }
  | { kind: "create" }
  | { kind: "edit"; skill: Skill }
  | { kind: "loading"; skillId: string; skillName: string };

type SkillFileEntry = { path: string; content: string };

const SKILL_ALLOWED_EXTENSIONS = [".md", ".txt", ".py", ".js", ".yaml", ".yml", ".json", ".sh", ".toml"];

function validateSkillFilePath(path: string): string | null {
  if (!path) return "文件路径不能为空";
  if (path.split("/").includes("..")) return "文件路径不能包含 '..'";
  if (path.startsWith("/")) return "文件路径不能以 '/' 开头";
  const lower = path.toLowerCase();
  if (!SKILL_ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
    return `文件后缀不允许（允许: ${SKILL_ALLOWED_EXTENSIONS.join(", ")}）`;
  }
  return null;
}

function validateSkillSlug(slug: string): string | null {
  if (!slug) return "slug 不能为空";
  if (slug.length > 128) return "slug 长度不能超过 128";
  if (slug.includes("..") || slug.includes("/") || slug.includes("\\")) {
    return "slug 不能包含 '..' / '/' / '\\'";
  }
  return null;
}

export function SkillsPanel() {
  const [list, setList] = useState<SkillListOut | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | false>(false);
  const [mode, setMode] = useState<SkillEditMode>({ kind: "closed" });

  useEffect(() => {
    let cancelled = false;
    productionServices.adminSkills.list()
      .then((data) => { if (!cancelled) setList(data); })
      .catch((err) => { if (!cancelled) setError(humanizeApiError(err)); });
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    if (!list) return [];
    const q = query.trim().toLowerCase();
    if (!q) return list.skills;
    return list.skills.filter(
      (s) => s.slug.toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
    );
  }, [list, query]);

  async function refreshList() {
    try {
      const data = await productionServices.adminSkills.list();
      setList(data);
    } catch (err) {
      setError(humanizeApiError(err));
    }
  }

  async function toggleEnabled(item: SkillListItem) {
    setBusy(`toggle:${item.id}`);
    setError("");
    setNotice("");
    try {
      await productionServices.adminSkills.update(item.id, { is_enabled: !item.is_enabled });
      setNotice(item.is_enabled ? `已停用 ${item.name}` : `已启用 ${item.name}`);
      await refreshList();
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeSkill(item: SkillListItem) {
    if (!window.confirm(`确认删除技能「${item.name}」？此操作不可撤销。`)) return;
    setBusy(`del:${item.id}`);
    setError("");
    setNotice("");
    try {
      await productionServices.adminSkills.remove(item.id);
      setNotice(`已删除 ${item.name}`);
      await refreshList();
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="production-admin-main">
      <header className="production-admin-heading">
        <div>
          <p>运营资产</p>
          <h1>技能管理</h1>
          <span>在此维护 Prompt Skills，启用后可在对话中按需被自动加载。</span>
        </div>
        <div className="production-admin-heading-actions">
          {list && (
            <span
              className={`production-admin-status ${
                list.enabled_count > 0 ? "positive" : "attention"
              }`}
            >
              <i aria-hidden="true" />
              {list.enabled_count > 0 ? "运行中" : "未启用"} · 共 {list.total} 项
            </span>
          )}
          <button
            className="primary-button"
            type="button"
            onClick={() => {
              setError("");
              setNotice("");
              setMode({ kind: "create" });
            }}
          >
            新建技能
          </button>
        </div>
      </header>

      <section className="harness-section skills-section">
        <header>
          <div>
            <small>SKILLS</small>
            <h2>已注册技能</h2>
          </div>
          <input
            type="search"
            placeholder="搜索 slug 或名称"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </header>

        {error && <p className="anspire-error" role="alert">{error}</p>}
        {notice && <p className="anspire-notice" role="status">{notice}</p>}

        {filtered.length === 0 ? (
          <p className="skills-empty">
            <strong>暂无技能</strong>
            点击右上角「新建技能」开始配置。
          </p>
        ) : (
          <table className="skills-list-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>Slug</th>
                <th>状态</th>
                <th>文件数</th>
                <th style={{ textAlign: "right" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id}>
                  <td>
                    <span className="name">
                      <strong>{item.name}</strong>
                      {item.description && <small>{item.description}</small>}
                    </span>
                  </td>
                  <td><span className="slug">{item.slug}</span></td>
                  <td>
                    <span className={`state ${item.is_enabled ? "on" : ""}`}>
                      <i aria-hidden="true" />
                      {item.is_enabled ? "启用" : "停用"}
                    </span>
                  </td>
                  <td><span className="count">{item.file_count}</span></td>
                  <td className="row-actions">
                    <div>
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={busy !== false}
                        onClick={() => {
                          setError("");
                          setNotice("");
                          setMode({ kind: "loading", skillId: item.id, skillName: item.name });
                          void loadSkillDetail(item.id);
                        }}
                      >
                        编辑
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={busy !== false}
                        onClick={() => void toggleEnabled(item)}
                      >
                        {item.is_enabled ? "停用" : "启用"}
                      </button>
                      <button
                        className="danger-button"
                        type="button"
                        disabled={busy !== false}
                        onClick={() => void removeSkill(item)}
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {mode.kind === "loading" && (
        <section className="skills-section-loading" aria-live="polite">
          <i aria-hidden="true" />
          正在加载「{mode.skillName}」…
        </section>
      )}
      {mode.kind !== "closed" && mode.kind !== "loading" && (
        <SkillEditor
          mode={mode}
          onClose={() => setMode({ kind: "closed" })}
          onSaved={async (msg) => {
            setNotice(msg);
            setMode({ kind: "closed" });
            await refreshList();
          }}
        />
      )}
    </main>
  );

  async function loadSkillDetail(skillId: string) {
    setBusy("load");
    setError("");
    try {
      const detail = await productionServices.adminSkills.get(skillId);
      setMode({ kind: "edit", skill: detail });
    } catch (err) {
      setError(humanizeApiError(err));
      setMode({ kind: "closed" });
    } finally {
      setBusy(false);
    }
  }
}

function SkillEditor({
  mode,
  onClose,
  onSaved,
}: {
  mode: Extract<SkillEditMode, { kind: "create" | "edit" }>;
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const isCreate = mode.kind === "create";
  const [slug, setSlug] = useState(mode.kind === "create" ? "" : mode.skill.slug);
  const [name, setName] = useState(mode.kind === "create" ? "" : mode.skill.name);
  const [description, setDescription] = useState(mode.kind === "create" ? "" : mode.skill.description);
  const [rootFile, setRootFile] = useState(mode.kind === "create" ? "SKILL.md" : mode.skill.root_file);
  const [isEnabled, setIsEnabled] = useState(mode.kind === "create" ? false : mode.skill.is_enabled);
  const [files, setFiles] = useState<SkillFileEntry[]>(() => {
    if (mode.kind === "edit") {
      return Object.entries(mode.skill.files).map(([path, content]) => ({ path, content }));
    }
    return [{ path: "SKILL.md", content: "# 新技能\n\n描述这个技能的用途。\n" }];
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [dropFeedback, setDropFeedback] = useState<{ ok: number; skipped: number; msg: string } | null>(null);

  function addFile() {
    setFiles((prev) => [...prev, { path: "", content: "" }]);
  }

  // ── 拖放文件夹：递归读取 entry，按相对路径合并进 files ──
  function readEntry(entry: FileSystemEntry, prefix: string): Promise<{ path: string; content: string }[]> {
    return new Promise((resolve) => {
      if (entry.isFile) {
        const fileEntry = entry as FileSystemFileEntry;
        fileEntry.file(
          (file) => {
            const path = prefix ? `${prefix}/${file.name}` : file.name;
            // 后缀白名单过滤（与后端 schemas/skill.py 一致）
            const lower = path.toLowerCase();
            if (!SKILL_ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
              resolve([]);
              return;
            }
            // 路径安全过滤
            if (path.split("/").includes("..") || path.startsWith("/") || path.includes("\\")) {
              resolve([]);
              return;
            }
            const reader = new FileReader();
            reader.onload = () => {
              resolve([{ path, content: String(reader.result ?? "") }]);
            };
            reader.onerror = () => resolve([]);
            reader.readAsText(file);
          },
          () => resolve([]),
        );
      } else if (entry.isDirectory) {
        const dirEntry = entry as FileSystemDirectoryEntry;
        const reader = dirEntry.createReader();
        const allEntries: FileSystemEntry[] = [];
        const readBatch = () => {
          reader.readEntries(
            async (batch) => {
              if (batch.length === 0) {
                // 递归处理所有子 entry
                const nested = await Promise.all(
                  allEntries.map((e) => readEntry(e, prefix ? `${prefix}/${entry.name}` : entry.name)),
                );
                resolve(nested.flat());
              } else {
                allEntries.push(...batch);
                readBatch(); // readEntries 一次最多返回 100 条，循环读到空
              }
            },
            () => resolve([]),
          );
        };
        readBatch();
      } else {
        resolve([]);
      }
    });
  }

  async function ingestDroppedItems(items: DataTransferItemList) {
    const entries: FileSystemEntry[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind !== "file") continue;
      const entry = item.webkitGetAsEntry?.();
      if (entry) entries.push(entry);
    }
    if (entries.length === 0) return;

    // 如果只拖入一个目录，默认剥掉顶层目录名，用其内部相对路径展示
    // （拖入 my-skill/SKILL.md → 路径为 "SKILL.md" 而非 "my-skill/SKILL.md"）
    // 拖入多个项目或单个文件时保持原行为
    let results: { path: string; content: string }[][];
    if (entries.length === 1 && entries[0].isDirectory) {
      const topDir = entries[0] as FileSystemDirectoryEntry;
      const reader = topDir.createReader();
      const childEntries: FileSystemEntry[] = [];
      const readAllBatches = (): Promise<void> =>
        new Promise((resolve) => {
          reader.readEntries(
            (batch) => {
              if (batch.length === 0) resolve();
              else {
                childEntries.push(...batch);
                readAllBatches().then(resolve);
              }
            },
            () => resolve(),
          );
        });
      await readAllBatches();
      results = await Promise.all(childEntries.map((e) => readEntry(e, "")));
    } else {
      results = await Promise.all(entries.map((e) => readEntry(e, "")));
    }
    const flat = results.flat();

    if (flat.length === 0) {
      setDropFeedback({ ok: 0, skipped: 0, msg: "未发现可导入的文件（仅支持 .md/.txt/.py/.js/.yaml/.yml/.json/.sh/.toml）" });
      return;
    }

    setFiles((prev) => {
      const map = new Map(prev.map((f) => [f.path, f]));
      let added = 0;
      let overwritten = 0;
      for (const f of flat) {
        if (map.has(f.path)) overwritten++;
        else added++;
        map.set(f.path, f);
      }
      const next = Array.from(map.values());
      // 如果当前 rootFile 不在列表中，且拖入了 SKILL.md，自动设为主入口
      const hasRoot = next.some((f) => f.path === rootFile);
      if (!hasRoot) {
        const skillMd = next.find((f) => f.path === "SKILL.md");
        if (skillMd) setRootFile("SKILL.md");
      }
      setDropFeedback({
        ok: added + overwritten,
        skipped: 0,
        msg: `已导入 ${added} 个新文件${overwritten > 0 ? `，覆盖 ${overwritten} 个同名文件` : ""}`,
      });
      return next;
    });
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!dragActive) setDragActive(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    // 只有离开拖放区本身才取消高亮（避免子元素触发）
    if (e.currentTarget === e.target) setDragActive(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setDropFeedback(null);
    const items = e.dataTransfer.items;
    if (items && items.length > 0) {
      void ingestDroppedItems(items);
    }
  }

  function updateFile(index: number, patch: Partial<SkillFileEntry>) {
    setFiles((prev) => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function validate(): string | null {
    if (isCreate) {
      const slugErr = validateSkillSlug(slug);
      if (slugErr) return slugErr;
    }
    if (!name.trim()) return "名称不能为空";
    if (!rootFile.trim()) return "主入口文件不能为空";
    const rootErr = validateSkillFilePath(rootFile);
    if (rootErr) return `主入口文件：${rootErr}`;
    const seenPaths = new Set<string>();
    for (const f of files) {
      const pathErr = validateSkillFilePath(f.path);
      if (pathErr) return `${f.path || "(空路径)"}: ${pathErr}`;
      if (seenPaths.has(f.path)) return `文件路径重复: ${f.path}`;
      seenPaths.add(f.path);
    }
    if (!files.some((f) => f.path === rootFile)) {
      return `主入口文件「${rootFile}」必须在文件列表中`;
    }
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setBusy(true);
    setError("");
    try {
      const filesMap: Record<string, string> = {};
      for (const f of files) filesMap[f.path] = f.content;
      if (isCreate) {
        const payload: SkillCreate = { slug, name, description, root_file: rootFile, is_enabled: isEnabled, files: filesMap };
        await productionServices.adminSkills.create(payload);
        onSaved(`已创建技能「${name}」`);
      } else {
        const payload: SkillUpdate = { name, description, root_file: rootFile, is_enabled: isEnabled, files: filesMap };
        await productionServices.adminSkills.update(mode.skill.id, payload);
        onSaved(`已保存技能「${name}」`);
      }
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="harness-section skills-section skills-editor-section">
      <header>
        <div>
          <small>{isCreate ? "CREATE" : "EDIT"}</small>
          <h2>{isCreate ? "新建技能" : `编辑：${mode.skill.name}`}</h2>
        </div>
        <button className="secondary-button" type="button" onClick={onClose}>关闭</button>
      </header>

      <form className="skills-editor-form" onSubmit={(e) => void handleSubmit(e)}>
        <div className="skills-editor-grid">
          <div className="skills-editor-field">
            <label htmlFor="skill-slug">
              Slug <span className="hint">唯一标识</span>
            </label>
            <input
              id="skill-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={!isCreate}
              spellCheck={false}
              autoComplete="off"
            />
            {!isCreate && <small>slug 创建后不可修改</small>}
          </div>

          <div className="skills-editor-field">
            <label htmlFor="skill-name">名称</label>
            <input
              id="skill-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="skills-editor-field span-full">
            <label htmlFor="skill-description">描述</label>
            <input
              id="skill-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="一句话概述这个技能的用途"
            />
          </div>

          <div className="skills-editor-field span-full">
            <label htmlFor="skill-root-file">
              主入口文件 <span className="hint">相对路径</span>
            </label>
            <input
              id="skill-root-file"
              value={rootFile}
              onChange={(e) => setRootFile(e.target.value)}
              spellCheck={false}
              autoComplete="off"
              placeholder="SKILL.md"
            />
            <small>必须在下方文件列表中存在</small>
          </div>
        </div>

        <div className="skills-editor-files">
          <div className="skills-editor-files-meta">
            <small>FILES</small>
            <h3>文件列表</h3>
            <button
              type="button"
              className="secondary-button"
              onClick={addFile}
              style={{ minHeight: "30px", padding: "0 10px", fontSize: "10.5px" }}
            >
              + 添加文件
            </button>
          </div>

          <div
            className={`skills-editor-dropzone${dragActive ? " dropzone-active" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="dropzone-content">
              <span className="dropzone-icon">📁</span>
              <span className="dropzone-hint">
                拖拽文件夹到此处导入（支持嵌套目录）
              </span>
              <small className="dropzone-allowed">
                允许: {SKILL_ALLOWED_EXTENSIONS.join(" ")}
              </small>
              {dropFeedback && (
                <span
                  className={`dropzone-feedback${dropFeedback.ok === 0 ? " dropzone-feedback-warn" : ""}`}
                  role="status"
                >
                  {dropFeedback.msg}
                </span>
              )}
            </div>
          </div>

          {files.map((f, i) => (
            <article key={i} className="skills-editor-file">
              <div className="skills-editor-file-meta-row">
                <span className="file-index">{i + 1}</span>
                <input
                  placeholder="相对路径，如 SKILL.md 或 tools/hello.md"
                  value={f.path}
                  onChange={(e) => updateFile(i, { path: e.target.value })}
                  spellCheck={false}
                  autoComplete="off"
                />
                <button
                  type="button"
                  className="danger-button file-remove"
                  style={{ minHeight: "30px", padding: "0 10px", fontSize: "10px" }}
                  onClick={() => removeFile(i)}
                >
                  删除文件
                </button>
              </div>
              <textarea
                className="skills-editor-file-content"
                placeholder="文件内容"
                value={f.content}
                onChange={(e) => updateFile(i, { content: e.target.value })}
              />
            </article>
          ))}
        </div>

        {error && <p className="anspire-error" role="alert">{error}</p>}

        <div className="skills-editor-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
            disabled={busy}
          >
            取消
          </button>
          <button
            type="submit"
            className="primary-button"
            disabled={busy}
          >
            {busy ? "保存中…" : (isCreate ? "创建技能" : "保存修改")}
          </button>
        </div>
      </form>
    </section>
  );
}
