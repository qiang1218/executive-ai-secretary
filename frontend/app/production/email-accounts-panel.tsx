"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { humanizeApiError } from "./api-client";
import { productionServices } from "./services";
import type {
  EmailAccount,
  EmailAccountCreate,
  EmailAccountTestOut,
  EmailAccountUpdate,
} from "./types";
import { formatAdminTime } from "./admin-shell-types";

type DraftMode = "create" | "edit" | null;

interface DraftState {
  mode: DraftMode;
  id?: string;
  address: string;
  display_name: string;
  protocol: "imap" | "pop3";
  server_host: string;
  server_port: number;
  use_tls: boolean;
  password: string;
  is_enabled: boolean;
}

function emptyDraft(): DraftState {
  return {
    mode: "create",
    address: "",
    display_name: "",
    protocol: "imap",
    server_host: "",
    server_port: 993,
    use_tls: true,
    password: "",
    is_enabled: true,
  };
}

function draftFromAccount(account: EmailAccount): DraftState {
  return {
    mode: "edit",
    id: account.id,
    address: account.address,
    display_name: account.display_name,
    protocol: account.protocol,
    server_host: account.server_host,
    server_port: account.server_port,
    use_tls: account.use_tls,
    password: "",
    is_enabled: account.is_enabled,
  };
}

export function EmailAccountsPanel() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | false>(false);
  const [syncingId, setSyncingId] = useState<string | false>(false);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await productionServices.emailAccounts.list(true);
      setAccounts(list);
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      if (draft.mode === "create") {
        const payload: EmailAccountCreate = {
          address: draft.address,
          display_name: draft.display_name || undefined,
          protocol: draft.protocol,
          server_host: draft.server_host,
          server_port: draft.server_port,
          use_tls: draft.use_tls,
          password: draft.password,
          is_enabled: draft.is_enabled,
        };
        await productionServices.emailAccounts.create(payload);
        setNotice("已新增邮件账户");
      } else if (draft.mode === "edit" && draft.id) {
        const payload: EmailAccountUpdate = {
          display_name: draft.display_name || undefined,
          protocol: draft.protocol,
          server_host: draft.server_host,
          server_port: draft.server_port,
          use_tls: draft.use_tls,
          is_enabled: draft.is_enabled,
        };
        if (draft.password) payload.password = draft.password;
        await productionServices.emailAccounts.update(draft.id, payload);
        setNotice("已更新邮件账户");
      }
      setDraft(null);
      await loadAccounts();
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    setError("");
    setNotice("");
    try {
      const result: EmailAccountTestOut = await productionServices.emailAccounts.test(id);
      setNotice(result.ok ? "连接测试通过" : `测试失败：${result.error_message || result.error_code || "未知错误"}`);
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setTestingId(false);
    }
  }

  async function handleSync(id: string) {
    setSyncingId(id);
    setError("");
    setNotice("");
    try {
      const result = await productionServices.emailAccounts.sync(id);
      setNotice(`已入队同步任务（job=${result.job_id}）`);
    } catch (err) {
      setError(humanizeApiError(err));
    } finally {
      setSyncingId(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("确定删除该邮件账户？相关 ScheduledTask 也会一并清理。")) return;
    setError("");
    setNotice("");
    try {
      await productionServices.emailAccounts.remove(id);
      setNotice("已删除邮件账户");
      await loadAccounts();
    } catch (err) {
      setError(humanizeApiError(err));
    }
  }

  return (
    <div className="page subpage production-email-page">
      <section className="page-heading split">
        <div>
          <p className="eyebrow">个人配置</p>
          <h1>我的邮箱</h1>
          <p>绑定 IMAP / POP3 邮箱后，系统按周期拉取新邮件并通过站内通知推送摘要。凭据加密存储，仅本人可访问。</p>
        </div>
        <div className="page-heading-actions">
          {accounts.length > 0 && (
            <span
              className={`production-admin-status ${
                accounts.some((a) => a.is_enabled) ? "positive" : "attention"
              }`}
            >
              <i aria-hidden="true" />
              {accounts.some((a) => a.is_enabled) ? "运行中" : "未启用"} · 共 {accounts.length} 项
            </span>
          )}
          <button
            type="button"
            className="primary-button"
            onClick={() => setDraft(emptyDraft())}
            disabled={draft !== null}
          >
            新增账户
          </button>
        </div>
      </section>

      {error && <p className="anspire-error" role="alert">{error}</p>}
      {notice && <p className="anspire-notice" role="status">{notice}</p>}

      {draft && (
        <section className="harness-section skills-editor-section email-editor">
          <header>
            <div>
              <small>{draft.mode === "create" ? "CREATE" : "EDIT"}</small>
              <h2>{draft.mode === "create" ? "新增邮件账户" : "编辑邮件账户"}</h2>
            </div>
            <button type="button" className="secondary-button" onClick={() => setDraft(null)} disabled={saving}>
              关闭
            </button>
          </header>
          <form className="skills-editor-form" onSubmit={handleSubmit}>
            <div className="skills-editor-grid">
              <div className="skills-editor-field">
                <label htmlFor="email-address">邮箱地址 <span className="hint">必填</span></label>
                <input
                  id="email-address"
                  type="email"
                  required
                  value={draft.address}
                  disabled={draft.mode === "edit"}
                  spellCheck={false}
                  autoComplete="off"
                  onChange={(e) => setDraft({ ...draft, address: e.target.value })}
                />
                {draft.mode === "edit" && <small>邮箱地址创建后不可修改</small>}
              </div>

              <div className="skills-editor-field">
                <label htmlFor="email-display-name">显示名称</label>
                <input
                  id="email-display-name"
                  type="text"
                  value={draft.display_name}
                  placeholder="如：个人邮箱"
                  onChange={(e) => setDraft({ ...draft, display_name: e.target.value })}
                />
              </div>

              <div className="skills-editor-field">
                <label htmlFor="email-protocol">协议</label>
                <select
                  id="email-protocol"
                  value={draft.protocol}
                  onChange={(e) => {
                    const protocol = e.target.value as "imap" | "pop3";
                    const port = protocol === "imap" ? 993 : 995;
                    setDraft({ ...draft, protocol, server_port: port });
                  }}
                >
                  <option value="imap">IMAP（推荐）</option>
                  <option value="pop3">POP3</option>
                </select>
              </div>

              <div className="skills-editor-field">
                <label htmlFor="email-server">服务器地址 <span className="hint">必填</span></label>
                <input
                  id="email-server"
                  type="text"
                  required
                  spellCheck={false}
                  autoComplete="off"
                  placeholder="如：imap.gmail.com"
                  value={draft.server_host}
                  onChange={(e) => setDraft({ ...draft, server_host: e.target.value })}
                />
              </div>

              <div className="skills-editor-field">
                <label htmlFor="email-port">端口</label>
                <input
                  id="email-port"
                  type="number"
                  min={1}
                  max={65535}
                  value={draft.server_port}
                  onChange={(e) => setDraft({ ...draft, server_port: Number(e.target.value) })}
                />
              </div>

              <div className="skills-editor-field">
                <label htmlFor="email-password">
                  密码 {draft.mode === "edit" && <span className="hint">留空不修改</span>}
                </label>
                <input
                  id="email-password"
                  type="password"
                  required={draft.mode === "create"}
                  value={draft.password}
                  autoComplete="new-password"
                  onChange={(e) => setDraft({ ...draft, password: e.target.value })}
                />
              </div>
            </div>

            <label className={`skills-editor-checkbox-row ${draft.is_enabled ? "is-on" : ""}`}>
              <input
                type="checkbox"
                checked={draft.use_tls}
                onChange={(e) => setDraft({ ...draft, use_tls: e.target.checked })}
              />
              <span>使用 TLS/SSL</span>
            </label>
            <label className={`skills-editor-checkbox-row ${draft.is_enabled ? "is-on" : ""}`}>
              <input
                type="checkbox"
                checked={draft.is_enabled}
                onChange={(e) => setDraft({ ...draft, is_enabled: e.target.checked })}
              />
              <span>{draft.is_enabled ? "保存后启用" : "保存为停用"}</span>
            </label>

            <div className="skills-editor-actions">
              <button type="button" className="secondary-button" onClick={() => setDraft(null)} disabled={saving}>
                取消
              </button>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "保存中…" : draft.mode === "create" ? "新增账户" : "保存修改"}
              </button>
            </div>
          </form>
        </section>
      )}

      {loading && accounts.length === 0 ? (
        <p className="skills-empty"><strong>加载中…</strong></p>
      ) : accounts.length === 0 ? (
        <p className="skills-empty">
          <strong>暂无邮件账户</strong>
          点击右上角「新增账户」开始配置。
        </p>
      ) : (
        <section className="harness-section skills-section">
          <header>
            <div>
              <small>EMAIL ACCOUNTS</small>
              <h2>已绑定邮箱</h2>
            </div>
          </header>
          <table className="skills-list-table">
            <thead>
              <tr>
                <th>邮箱</th>
                <th>协议</th>
                <th>服务器</th>
                <th>状态</th>
                <th>最近同步</th>
                <th>最近错误</th>
                <th style={{ textAlign: "right" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>
                    <span className="name">
                      <strong>{account.display_name || account.address}</strong>
                      <small>{account.address}</small>
                    </span>
                  </td>
                  <td>{account.protocol.toUpperCase()}</td>
                  <td>
                    <span className="slug">
                      {account.server_host}:{account.server_port}
                      {account.use_tls ? " · TLS" : ""}
                    </span>
                  </td>
                  <td>
                    <span className={`state ${account.is_enabled ? "on" : ""}`}>
                      <i aria-hidden="true" />
                      {account.is_enabled ? "启用" : "停用"}
                    </span>
                  </td>
                  <td>{formatAdminTime(account.last_synced_at ?? null)}</td>
                  <td>
                    {account.last_error_code ? (
                      <span className="email-error-chip" title={account.last_error_message || ""}>
                        {account.last_error_code}
                      </span>
                    ) : (
                      <span className="email-error-empty">—</span>
                    )}
                  </td>
                  <td className="row-actions">
                    <div>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => setDraft(draftFromAccount(account))}
                        disabled={draft !== null}
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => void handleTest(account.id)}
                        disabled={testingId === account.id}
                      >
                        {testingId === account.id ? "测试中…" : "测试"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => void handleSync(account.id)}
                        disabled={syncingId === account.id || !account.is_enabled}
                      >
                        {syncingId === account.id ? "入队中…" : "立即同步"}
                      </button>
                      <button
                        type="button"
                        className="danger-button"
                        onClick={() => void handleDelete(account.id)}
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
