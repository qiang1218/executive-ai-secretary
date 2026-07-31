"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, humanizeApiError } from "./api-client";
import { adminServices } from "./admin-services";
import type {
  AdminAuditEvent,
  AdminBootstrap,
  AdminOrganizationUnit,
  AdminRuntimeStatus,
  AdminSection,
  AdminUser,
  AuthMe,
} from "./types";
import { adminNavigation } from "./types";

type Tone = "positive" | "attention" | "risk" | "neutral";

type AdminWorkspaceProps = {
  me: AuthMe;
  bootstrap: AdminBootstrap | null;
  onLogout: () => void | Promise<void>;
  onRefresh?: () => Promise<AdminBootstrap>;
};

function toneFromOutcome(outcome: string): Tone {
  if (outcome === "success") return "positive";
  if (outcome === "failure") return "risk";
  return "neutral";
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  const pad = (n: number) => `${n}`.padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function describeRuntimeStatus(runtime: AdminRuntimeStatus | null): { tone: Tone; label: string } {
  if (!runtime) return { tone: "attention", label: "等待数据" };
  if (runtime.database === "healthy" && !runtime.demo_data_enabled) return { tone: "positive", label: "运行正常" };
  if (runtime.database === "healthy") return { tone: "positive", label: "运行正常（演示数据）" };
  return { tone: "risk", label: `数据库异常：${runtime.database}` };
}

function StatusBadge({ tone, label }: { tone: Tone; label: string }) {
  return <span className={`status-badge ${tone}`}>{label}</span>;
}

function Toast({ message }: { message: string }) {
  return (
    <div className="toast" role="status" aria-live="polite">
      <span className="status-dot positive" aria-hidden="true" />
      {message}
    </div>
  );
}

export async function loadAdminBootstrap(): Promise<AdminBootstrap> {
  const [runtimeResult, unitsResult, usersResult] = await Promise.allSettled([
    adminServices.runtime.get(),
    adminServices.organizationUnits.list(),
    adminServices.users.list(),
  ]);
  return {
    runtime: runtimeResult.status === "fulfilled" ? runtimeResult.value : null,
    runtimeError: runtimeResult.status === "rejected" ? humanizeApiError(runtimeResult.reason) : null,
    organizationUnits: unitsResult.status === "fulfilled" ? unitsResult.value.items : [],
    users: usersResult.status === "fulfilled" ? usersResult.value.items : [],
    usersError: usersResult.status === "rejected" ? humanizeApiError(usersResult.reason) : null,
  };
}

function roleLabel(role: AuthMe["user"]["role"]): string {
  if (role === "enterprise_admin") return "企业管理员";
  if (role === "fde") return "现场工程师";
  return "管理员";
}

export function AdminWorkspace({ me, bootstrap, onLogout, onRefresh }: AdminWorkspaceProps) {
  const [section, setSection] = useState<AdminSection>("overview");
  const [toast, setToast] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [adminData, setAdminData] = useState<AdminBootstrap>(bootstrap ?? {
    runtime: null,
    runtimeError: null,
    organizationUnits: [],
    users: [],
    usersError: null,
  });
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);
  const notify = (message: string) => setToast(message);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const next = onRefresh ? await onRefresh() : await loadAdminBootstrap();
      setAdminData(next);
      notify("管理端数据已刷新");
    } catch (error) {
      notify(`刷新失败：${humanizeApiError(error)}`);
    } finally {
      setRefreshing(false);
    }
  }, [onRefresh]);

  return (
    <div
      className="product-shell admin-shell"
      data-app-mode={me.app_mode}
      data-app-environment={me.app_env}
    >
      <a className="skip-link" href="#admin-main">跳到主要内容</a>
      <header className="app-header">
        <button type="button" className="brand-button" onClick={() => setSection("overview")}>
          <span className="brand-glyph admin" aria-hidden="true">管</span>
          <span>
            <strong>AI 秘书管理端</strong>
            <small>企业管理员与 FDE</small>
          </span>
        </button>
        <nav className="primary-nav admin-nav" aria-label="管理端主导航">
          {adminNavigation.map((item) => (
            <button
              type="button"
              key={item.id}
              className={section === item.id ? "active" : ""}
              aria-current={section === item.id ? "page" : undefined}
              onClick={() => setSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="profile-control">
          <button
            type="button"
            className="profile-button"
            aria-label="打开管理员菜单"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen((current) => !current)}
          >
            <span aria-hidden="true">管</span>
            <span>
              <strong>{roleLabel(me.user.role)}</strong>
              <small>{me.enterprise.name}</small>
            </span>
          </button>
          {profileOpen && (
            <div className="profile-menu">
              <button type="button" onClick={() => { setProfileOpen(false); setSection("account"); }}>
                账号设置
              </button>
              <button type="button" onClick={() => { setProfileOpen(false); void onLogout(); }}>
                退出管理端
              </button>
            </div>
          )}
        </div>
      </header>
      <main id="admin-main" className="app-main admin-main">
        {section === "overview" && (
          <AdminOverview
            data={adminData}
            me={me}
            refreshing={refreshing}
            onNavigate={setSection}
            onRefresh={refresh}
          />
        )}
        {section === "account" && (
          <AdminAccount
            data={adminData}
            me={me}
            onBack={() => setSection("overview")}
            onNotify={notify}
            onDataChange={setAdminData}
          />
        )}
        {section === "model" && <AdminModel onNotify={notify} />}
        {section === "source" && (
          <AdminSource
            data={adminData}
            me={me}
            onBack={() => setSection("overview")}
            onNotify={notify}
          />
        )}
        {section === "automation" && <AdminAutomation onNotify={notify} />}
        {section === "feishu" && <AdminFeishu onNotify={notify} />}
        {section === "capability" && <AdminCapabilities onNotify={notify} />}
        {section === "runtime" && (
          <AdminRuntime data={adminData} me={me} onNotify={notify} />
        )}
      </main>
      <nav className="mobile-nav admin-mobile-nav" aria-label="管理端移动导航">
        {adminNavigation.map((item) => (
          <button
            type="button"
            key={item.id}
            className={section === item.id ? "active" : ""}
            onClick={() => setSection(item.id)}
          >
            <span>{item.short.slice(0, 1)}</span>{item.short}
          </button>
        ))}
      </nav>
      {toast && <Toast message={toast} />}
    </div>
  );
}

function AdminOverview({ data, me, refreshing, onNavigate, onRefresh }: {
  data: AdminBootstrap;
  me: AuthMe;
  refreshing: boolean;
  onNavigate: (section: AdminSection) => void;
  onRefresh: () => Promise<void>;
}) {
  const runtimeTone = describeRuntimeStatus(data.runtime);
  const unitsReady = data.organizationUnits.filter(
    (unit) => unit.enabled_for_analysis && unit.data_connected,
  ).length;
  const usersByRole = useMemo(() => {
    const map = new Map<string, number>();
    for (const user of data.users) map.set(user.role, (map.get(user.role) ?? 0) + 1);
    return map;
  }, [data.users]);
  const statuses: Array<{ name: string; status: string; tone: Tone; target: AdminSection; detail: string }> = [
    {
      name: "应用版本",
      status: data.runtime ? `${data.runtime.app_env} · ${data.runtime.version}` : "未连接",
      tone: data.runtime ? "positive" : "attention",
      target: "runtime",
      detail: data.runtime ? `当前模式 ${data.runtime.app_mode}` : "运行状态接口暂不可用",
    },
    {
      name: "数据库",
      status: data.runtime?.database ?? "未知",
      tone: data.runtime?.database === "healthy" ? "positive" : "risk",
      target: "runtime",
      detail: data.runtime ? `存储 ${data.runtime.storage}` : "请稍后重试",
    },
    {
      name: "高层账号",
      status: `${usersByRole.get("executive") ?? 0} 位`,
      tone: "positive",
      target: "account",
      detail: `总账号 ${data.users.length}`,
    },
    {
      name: "可用组织单元",
      status: `${unitsReady} 个`,
      tone: unitsReady > 0 ? "positive" : "attention",
      target: "source",
      detail: `全部 ${data.organizationUnits.length} 个`,
    },
    {
      name: "演示数据",
      status: data.runtime?.demo_data_enabled ? "启用" : "关闭",
      tone: data.runtime?.demo_data_enabled ? "attention" : "positive",
      target: "runtime",
      detail: "影响回答可观测性",
    },
  ];
  return (
    <div className="page subpage admin-page">
      <section className="page-heading split">
        <div>
          <p className="eyebrow">系统总览</p>
          <h1>五项核心状态</h1>
          <p>这里只展示可操作摘要，完整日志和高层会话正文不会出现在总览。</p>
        </div>
        <span className="last-check">
          {data.runtime ? `最近检查 ${formatTimestamp(new Date().toISOString())}` : "等待首次连接"}
        </span>
      </section>
      {data.runtimeError && <p className="form-error">{data.runtimeError}</p>}
      <section className="admin-status-grid">
        {statuses.map((entry, index) => (
          <button type="button" key={entry.name} onClick={() => onNavigate(entry.target)}>
            <span className="status-index">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <small>{entry.name}</small>
              <strong>{entry.status}</strong>
              <span>{entry.detail}</span>
            </div>
            <StatusBadge
              tone={entry.tone}
              label={entry.tone === "positive" ? "正常" : entry.tone === "risk" ? "需关注" : "关注"}
            />
          </button>
        ))}
      </section>
      <div className="admin-overview-grid">
        <section>
          <header className="section-header">
            <div>
              <p className="eyebrow">最近任务</p>
              <h2>运行记录</h2>
            </div>
            <button type="button" className="text-button" onClick={() => onNavigate("automation")}>查看任务</button>
          </header>
          <div className="simple-list">
            <div>
              <time>—</time>
              <span><strong>暂无后台任务记录</strong><small>完整记录请在运行状态中查看</small></span>
              <StatusBadge tone={runtimeTone.tone} label={runtimeTone.label} />
            </div>
            <div>
              <time>—</time>
              <span><strong>暂无自动任务执行历史</strong><small>请等待每日 02:00 之后的首次同步</small></span>
              <StatusBadge tone="neutral" label="—" />
            </div>
          </div>
        </section>
        <section>
          <header className="section-header">
            <div>
              <p className="eyebrow">账号</p>
              <h2>当前登录</h2>
            </div>
            <button type="button" className="text-button" onClick={() => onNavigate("account")}>管理账号</button>
          </header>
          <dl className="overview-account">
            <div><dt>账号</dt><dd>{me.user.email}</dd></div>
            <div><dt>显示名</dt><dd>{me.user.display_name}</dd></div>
            <div><dt>角色</dt><dd><StatusBadge tone="positive" label={roleLabel(me.user.role)} /></dd></div>
            <div>
              <dt>密码策略</dt>
              <dd>
                <StatusBadge
                  tone={me.user.password_change_required ? "attention" : "positive"}
                  label={me.user.password_change_required ? "首次登录待修改" : "已设置"}
                />
              </dd>
            </div>
            <div><dt>企业</dt><dd>{me.enterprise.name}</dd></div>
            <div>
              <dt>上次同步</dt>
              <dd>
                <button type="button" className="text-button" onClick={() => { void onRefresh(); }} disabled={refreshing}>
                  {refreshing ? "刷新中" : "立即刷新"}
                </button>
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  );
}

function AdminAccount({ data, me, onBack, onNotify, onDataChange }: {
  data: AdminBootstrap;
  me: AuthMe;
  onBack: () => void;
  onNotify: (message: string) => void;
  onDataChange: (next: AdminBootstrap) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [draftEmail, setDraftEmail] = useState("");
  const [draftName, setDraftName] = useState("");
  const [draftPassword, setDraftPassword] = useState("");
  const [draftRole, setDraftRole] = useState<AdminUser["role"]>("executive");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const users = data.users;

  async function reload() {
    try {
      const next = await loadAdminBootstrap();
      onDataChange(next);
    } catch (error) {
      onNotify(`刷新账号失败：${humanizeApiError(error)}`);
    }
  }

  async function toggleActive(user: AdminUser) {
    try {
      await adminServices.users.update(user.id, { is_active: !user.password_change_required });
      onNotify(`${user.display_name} 状态已切换`);
      await reload();
    } catch (error) {
      onNotify(`更新失败：${humanizeApiError(error)}`);
    }
  }

  async function resetPassword(user: AdminUser) {
    const temp = window.prompt(`为 ${user.display_name} 设置新的临时密码（至少 10 个字符）`);
    if (!temp) return;
    if (temp.length < 10) { onNotify("临时密码长度至少 10 个字符"); return; }
    try {
      await adminServices.users.resetPassword(user.id, temp);
      onNotify(`已为 ${user.display_name} 重置临时密码，首次登录必须修改`);
      await reload();
    } catch (error) {
      onNotify(`重置失败：${humanizeApiError(error)}`);
    }
  }

  async function revokeSessions(user: AdminUser) {
    try {
      await adminServices.users.revokeSessions(user.id);
      onNotify(`${user.display_name} 的全部登录会话已失效`);
      await reload();
    } catch (error) {
      onNotify(`操作失败：${humanizeApiError(error)}`);
    }
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!draftEmail.includes("@")) { setFormError("请输入有效邮箱"); return; }
    if (!draftName.trim()) { setFormError("请输入显示名"); return; }
    if (draftPassword.length < 10) { setFormError("临时密码长度至少 10 个字符"); return; }
    setSubmitting(true);
    try {
      await adminServices.users.create({
        email: draftEmail.trim(),
        display_name: draftName.trim(),
        role: draftRole,
        temporary_password: draftPassword,
        organization_unit_ids: [],
        enterprise_wide_scope: draftRole === "executive",
      });
      onNotify(`${draftName} 已创建，首次登录必须修改密码`);
      setCreating(false);
      setDraftEmail(""); setDraftName(""); setDraftPassword(""); setDraftRole("executive");
      await reload();
    } catch (error) {
      setFormError(humanizeApiError(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page subpage admin-page">
      <section className="page-heading split">
        <div>
          <button type="button" className="back-link" onClick={onBack}>返回总览</button>
          <p className="eyebrow">账号与登录</p>
          <h1>账号管理</h1>
          <p>管理员不能查看高层完整会话、长期记忆或上传文件正文。</p>
        </div>
        <button type="button" className="primary-button" onClick={() => setCreating((current) => !creating)}>
          {creating ? "取消新建" : "新建账号"}
        </button>
      </section>
      {data.usersError && <p className="form-error">{data.usersError}</p>}
      {creating && (
        <section className="settings-section">
          <header className="section-header">
            <div><p className="eyebrow">新建账号</p><h2>创建企业账号</h2></div>
            <StatusBadge tone={submitting ? "attention" : "neutral"} label={submitting ? "提交中" : "草稿"} />
          </header>
          <form className="settings-grid" onSubmit={submitCreate}>
            <label className="field"><span>邮箱（登录名）</span><input type="email" value={draftEmail} onChange={(e) => setDraftEmail(e.target.value)} autoComplete="off" required /></label>
            <label className="field"><span>显示名</span><input value={draftName} onChange={(e) => setDraftName(e.target.value)} required /></label>
            <label className="field">
              <span>角色</span>
              <select value={draftRole} onChange={(e) => setDraftRole(e.target.value as AdminUser["role"])}>
                <option value="executive">executive（高层）</option>
                <option value="enterprise_admin">enterprise_admin（企业管理员）</option>
                <option value="fde">fde（现场工程师）</option>
              </select>
            </label>
            <label className="field"><span>临时密码（至少 10 位）</span><input type="password" value={draftPassword} onChange={(e) => setDraftPassword(e.target.value)} autoComplete="new-password" required /></label>
            {formError && <p className="form-error" role="alert">{formError}</p>}
            <div className="settings-actions">
              <button type="button" className="secondary-button" onClick={() => setCreating(false)}>取消</button>
              <button type="submit" className="primary-button" disabled={submitting}>{submitting ? "提交中" : "创建账号"}</button>
            </div>
          </form>
        </section>
      )}
      <section className="settings-section">
        <header className="section-header">
          <div><p className="eyebrow">本企业账号</p><h2>{users.length} 位用户</h2></div>
          <span>当前账号 {me.user.email}</span>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>账号</th><th>显示名</th><th>角色</th><th>首次登录</th><th>操作</th></tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td><strong>{user.email}</strong>{user.id === me.user.id && <small> · 当前</small>}</td>
                  <td>{user.display_name}</td>
                  <td><StatusBadge tone={user.role === "executive" ? "positive" : "attention"} label={roleLabel(user.role)} /></td>
                  <td><StatusBadge tone={user.password_change_required ? "attention" : "positive"} label={user.password_change_required ? "待修改" : "已设置"} /></td>
                  <td>
                    <div className="row-actions">
                      <button type="button" className="secondary-button" onClick={() => void resetPassword(user)} disabled={user.id === me.user.id}>重置密码</button>
                      <button type="button" className="secondary-button" onClick={() => void toggleActive(user)} disabled={user.id === me.user.id}>切换状态</button>
                      <button type="button" className="danger-text-button" onClick={() => void revokeSessions(user)} disabled={user.id === me.user.id}>失效会话</button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && <tr><td colSpan={5}>暂无账号</td></tr>}
            </tbody>
          </table>
        </div>
        <aside className="privacy-note"><strong>默认隐私边界</strong><p>企业管理员只能管理账号状态，不能直接读取高层会话、长期记忆和文件正文。如需审计权限，必须单独配置并明确告知高层用户。</p></aside>
      </section>
    </div>
  );
}

function AdminModel({ onNotify }: { onNotify: (message: string) => void }) {
  const [model, setModel] = useState("Qwen3-32B 本地模型");
  const [tested, setTested] = useState(false);
  const [testing, setTesting] = useState(false);
  function test() {
    setTesting(true);
    window.setTimeout(() => { setTesting(false); setTested(true); onNotify("连接测试通过，响应 842ms"); }, 850);
  }
  return (
    <div className="page subpage admin-page">
      <section className="page-heading">
        <p className="eyebrow">一次只启用一个</p>
        <h1>模型配置</h1>
        <p>首版演示 UI。模型配置写入与切换的接口尚在建设中，先沿用 demo 中的设置面板。</p>
      </section>
      <section className="settings-section">
        <header className="section-header">
          <div><p className="eyebrow">当前配置</p><h2>经营助理主模型</h2></div>
          <StatusBadge tone={tested ? "positive" : "attention"} label={tested ? "测试通过" : "等待测试"} />
        </header>
        <div className="settings-grid">
          <label className="field"><span>配置名称</span><input defaultValue="经营助理主模型" /></label>
          <label className="field"><span>模型类型</span><select defaultValue="本地大模型"><option>云端大模型</option><option>本地大模型</option><option>本地小模型</option></select></label>
          <label className="field wide"><span>API Base URL</span><input defaultValue="http://model-gateway:8000/v1" /></label>
          <label className="field"><span>API Key</span><input type="password" value="sk-demo-masked-key" readOnly /></label>
          <label className="field">
            <span>模型名称</span>
            <select value={model} onChange={(event) => { setModel(event.target.value); setTested(false); }}>
              <option>Qwen3-32B 本地模型</option>
              <option>云端兼容模型</option>
              <option>Qwen3-8B 本地小模型</option>
            </select>
          </label>
          <label className="field"><span>超时时间</span><input type="number" defaultValue={120} /></label>
          <label className="field"><span>最大输出长度</span><input type="number" defaultValue={8192} /></label>
          <label className="field"><span>温度，可选</span><input type="number" step={0.1} defaultValue={0.2} /></label>
        </div>
        <div className="settings-actions">
          <button type="button" className="secondary-button" onClick={test} disabled={testing}>{testing ? "正在测试" : "测试连接"}</button>
          <button type="button" className="primary-button" disabled={!tested} onClick={() => onNotify(`${model} 已设为当前模型（演示）`)}>保存并设为当前模型</button>
        </div>
        <p className="settings-footnote">最近测试：{tested ? "刚刚" : "未测试"} · 演示占位 UI，模型配置 API 待对接。</p>
      </section>
    </div>
  );
}

function AdminSource({ data, me, onBack, onNotify }: {
  data: AdminBootstrap;
  me: AuthMe;
  onBack: () => void;
  onNotify: (message: string) => void;
}) {
  const [tab, setTab] = useState<"connection" | "mapping" | "sync" | "simulation">("connection");
  const [syncing, setSyncing] = useState(false);
  const units = data.organizationUnits;
  const connectedUnits = units.filter((unit) => unit.data_connected);
  const readyUnits = units.filter((unit) => unit.enabled_for_analysis && unit.data_connected);
  function runSync() {
    setSyncing(true);
    window.setTimeout(() => { setSyncing(false); onNotify(`同步完成：已连接 ${connectedUnits.length} 个组织单元`); }, 950);
  }
  return (
    <div className="page subpage admin-page">
      <section className="page-heading">
        <button type="button" className="back-link" onClick={onBack}>返回总览</button>
        <p className="eyebrow">组织与数据范围</p>
        <h1>数据源</h1>
        <p>连接、字段映射、同步与模拟数据状态在一个流程中完成。</p>
      </section>
      <div className="subnav" role="tablist">
        {([["connection", "连接与组织"], ["mapping", "字段映射"], ["sync", "同步记录"], ["simulation", "模拟数据"]] as const).map(([id, label]) => (
          <button type="button" role="tab" key={id} aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {data.runtimeError && tab === "connection" && <p className="form-error">运行状态接口异常：{data.runtimeError}</p>}
      {tab === "connection" && (
        <section className="settings-section">
          <header className="section-header">
            <div><p className="eyebrow">本企业组织</p><h2>{units.length} 个组织单元</h2></div>
            <StatusBadge tone={connectedUnits.length > 0 ? "positive" : "attention"} label={connectedUnits.length > 0 ? "已连接" : "未连接"} />
          </header>
          <div className="table-wrap">
            <table>
              <thead><tr><th>编号</th><th>名称</th><th>类型</th><th>数据连接</th><th>启用分析</th></tr></thead>
              <tbody>
                {units.map((unit: AdminOrganizationUnit) => (
                  <tr key={unit.id}>
                    <td><code>{unit.code}</code></td>
                    <td>{unit.name}</td>
                    <td>{unit.unit_type}</td>
                    <td><StatusBadge tone={unit.data_connected ? "positive" : "neutral"} label={unit.data_connected ? "已连接" : "未连接"} /></td>
                    <td><StatusBadge tone={unit.enabled_for_analysis ? "positive" : "attention"} label={unit.enabled_for_analysis ? "已启用" : "未启用"} /></td>
                  </tr>
                ))}
                {units.length === 0 && <tr><td colSpan={5}>本企业尚未配置组织单元。</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="settings-actions">
            <button type="button" className="secondary-button" onClick={() => onNotify(`已就绪 ${readyUnits.length} 个组织单元，可被高层查询`)}>查看可查询范围</button>
            <button type="button" className="primary-button" onClick={() => setTab("mapping")}>进入字段映射</button>
          </div>
        </section>
      )}
      {tab === "mapping" && (
        <section className="settings-section mapping-section">
          <header className="section-header">
            <div><p className="eyebrow">映射配置</p><h2>字段映射</h2></div>
            <StatusBadge tone={units.length > 0 ? "positive" : "risk"} label={units.length > 0 ? `${units.length} 个单元就绪` : "尚未配置组织"} />
          </header>
          <p className="settings-footnote">字段映射的高级配置（V3 版本同步、计划回款日校验等）首版演示 UI，后续将接入后端接口。当前以组织单元的就绪状态作为映射完整性提示。</p>
          <div className="settings-actions">
            <button type="button" className="primary-button" onClick={() => setTab("sync")}>保存并启用同步</button>
          </div>
        </section>
      )}
      {tab === "sync" && (
        <section className="settings-section">
          <header className="section-header">
            <div><p className="eyebrow">同步状态</p><h2>数据同步</h2></div>
            <button type="button" className="primary-button" onClick={runSync} disabled={syncing}>{syncing ? "正在同步" : "手动同步"}</button>
          </header>
          <dl className="overview-account">
            <div><dt>已连接单元</dt><dd>{connectedUnits.length}</dd></div>
            <div><dt>可分析单元</dt><dd>{readyUnits.length}</dd></div>
            <div><dt>当前用户企业</dt><dd>{me.enterprise.name}</dd></div>
          </dl>
          <p className="settings-footnote">管理端只读同步，不允许直接编辑飞书源数据。</p>
        </section>
      )}
      {tab === "simulation" && (
        <section className="settings-section">
          <header className="section-header">
            <div><p className="eyebrow">固定演示版本</p><h2>模拟数据状态</h2></div>
            <span>{data.runtime?.demo_data_enabled ? "演示数据已启用" : "演示数据已关闭"}</span>
          </header>
          <div className="simulation-list">
            <article>
              <div><h3>演示种子</h3><p>由后端 demo 数据生成器提供</p></div>
              <StatusBadge tone={data.runtime?.demo_data_enabled ? "positive" : "neutral"} label={data.runtime?.demo_data_enabled ? "已启用" : "已关闭"} />
            </article>
            <article>
              <div><h3>组织映射</h3><p>本企业组织单元来自 {me.enterprise.slug}</p></div>
              <StatusBadge tone={units.length > 0 ? "positive" : "attention"} label={units.length > 0 ? "已建立" : "尚未建立"} />
            </article>
          </div>
          <aside className="privacy-note"><strong>重建控制</strong><p>模拟数据生成与重置只通过 FDE 部署工具执行，企业管理员不能在演示过程中随意重建。</p></aside>
        </section>
      )}
    </div>
  );
}

function AdminAutomation({ onNotify }: { onNotify: (message: string) => void }) {
  const [syncTime, setSyncTime] = useState("02:00");
  const [dailyTime, setDailyTime] = useState("05:00");
  const [dailyPush, setDailyPush] = useState("07:30");
  const [weeklyTime, setWeeklyTime] = useState("06:00");
  const [weeklyPush, setWeeklyPush] = useState("07:45");
  const [pushEnabled, setPushEnabled] = useState(true);
  const conflict = dailyTime <= syncTime || dailyPush <= dailyTime || weeklyPush <= weeklyTime;
  return (
    <div className="page subpage admin-page">
      <section className="page-heading">
        <p className="eyebrow">生成与推送分离</p>
        <h1>自动任务</h1>
        <p>首版演示 UI。时间配置保存在本地浏览器中，不会写入后端。</p>
      </section>
      <div className="automation-grid">
        <section className="settings-section">
          <header className="section-header">
            <div><p className="eyebrow">每天</p><h2>每日经营变化</h2></div>
            <StatusBadge tone={pushEnabled ? "positive" : "attention"} label={pushEnabled ? "已启用" : "仅生成不推送"} />
          </header>
          <div className="settings-grid one-column">
            <label className="field"><span>数据同步时间</span><input type="time" value={syncTime} onChange={(e) => setSyncTime(e.target.value)} /></label>
            <label className="field"><span>摘要生成时间</span><input type="time" value={dailyTime} onChange={(e) => setDailyTime(e.target.value)} /></label>
            <label className="field"><span>飞书推送时间</span><input type="time" value={dailyPush} onChange={(e) => setDailyPush(e.target.value)} /></label>
            <label className="check-row">
              <input type="checkbox" checked={pushEnabled} onChange={(e) => setPushEnabled(e.target.checked)} />
              <span><strong>启用每日飞书推送</strong><small>关闭后摘要仍保存在 H5</small></span>
            </label>
          </div>
        </section>
        <section className="settings-section">
          <header className="section-header">
            <div><p className="eyebrow">每周一</p><h2>每周高层简报</h2></div>
            <StatusBadge tone="positive" label="已启用" />
          </header>
          <div className="settings-grid one-column">
            <label className="field"><span>生成星期</span><select defaultValue="周一"><option>周一</option></select></label>
            <label className="field"><span>简报生成时间</span><input type="time" value={weeklyTime} onChange={(e) => setWeeklyTime(e.target.value)} /></label>
            <label className="field"><span>飞书推送时间</span><input type="time" value={weeklyPush} onChange={(e) => setWeeklyPush(e.target.value)} /></label>
          </div>
        </section>
      </div>
      {conflict && <p className="form-error task-conflict">时间配置冲突：生成必须晚于同步，推送必须晚于对应内容生成。</p>}
      <div className="settings-actions">
        <button type="button" className="primary-button" disabled={conflict} onClick={() => onNotify("自动任务配置已保存到浏览器（演示）")}>保存配置</button>
      </div>
    </div>
  );
}

function AdminFeishu({ onNotify }: { onNotify: (message: string) => void }) {
  const [testing, setTesting] = useState(false);
  function test() {
    setTesting(true);
    window.setTimeout(() => { setTesting(false); onNotify("测试消息发送成功（演示）"); }, 850);
  }
  return (
    <div className="page subpage admin-page">
      <section className="page-heading">
        <p className="eyebrow">只推送每日与每周内容</p>
        <h1>飞书推送</h1>
        <p>首版演示 UI。飞书凭证写入与接收人配置待接入后端。</p>
      </section>
      <section className="settings-section">
        <header className="section-header">
          <div><p className="eyebrow">连接配置</p><h2>飞书应用</h2></div>
          <StatusBadge tone="positive" label="已连接" />
        </header>
        <div className="settings-grid">
          <label className="field"><span>飞书应用 ID</span><input defaultValue="cli_a7f••••••9c2" /></label>
          <label className="field"><span>应用密钥</span><input type="password" value="feishu-masked-secret" readOnly /></label>
          <label className="field"><span>接收用户 Open ID</span><input defaultValue="ou_demo_chairman_01" /></label>
          <label className="field"><span>H5 外部访问地址</span><input defaultValue="https://chairman-assistant.example.invalid" /></label>
          <label className="field wide"><span>消息模板</span><select defaultValue="高层经营摘要 V1"><option>高层经营摘要 V1</option></select></label>
        </div>
        <div className="settings-actions">
          <button type="button" className="secondary-button" onClick={test} disabled={testing}>{testing ? "正在发送" : "测试发送"}</button>
          <button type="button" className="primary-button" onClick={() => onNotify("飞书推送配置已保存（演示）")}>保存配置</button>
        </div>
      </section>
    </div>
  );
}

function AdminCapabilities({ onNotify }: { onNotify: (message: string) => void }) {
  const tools = [
    { name: "经营总览查询", version: "1.3.0", scope: "经营数据", enabled: true, lastTest: "通过" },
    { name: "商机与预测", version: "1.2.4", scope: "经营数据", enabled: true, lastTest: "通过" },
    { name: "项目交付查询", version: "1.1.8", scope: "经营数据", enabled: true, lastTest: "通过" },
    { name: "回款与现金", version: "1.0.9", scope: "经营数据", enabled: true, lastTest: "通过" },
    { name: "当前会话文档", version: "2.0.1", scope: "文件", enabled: true, lastTest: "通过" },
    { name: "公开搜索", version: "1.4.2", scope: "泛化", enabled: true, lastTest: "842ms" },
  ];
  return (
    <div className="page subpage admin-page">
      <section className="page-heading">
        <p className="eyebrow">受控暴露</p>
        <h1>能力白名单</h1>
        <p>首版演示 UI。启停状态由后端 capability registry 提供，本页面仅展示。</p>
      </section>
      <div className="table-wrap">
        <table>
          <thead><tr><th>能力</th><th>版本</th><th>适用范围</th><th>最近测试</th><th>状态</th></tr></thead>
          <tbody>
            {tools.map((tool) => (
              <tr key={tool.name}>
                <td><strong>{tool.name}</strong></td>
                <td>{tool.version}</td>
                <td>{tool.scope}</td>
                <td>{tool.lastTest}</td>
                <td><StatusBadge tone={tool.enabled ? "positive" : "attention"} label={tool.enabled ? "启用" : "停用"} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="settings-actions">
        <button type="button" className="primary-button" onClick={() => onNotify("能力白名单状态已刷新（演示）")}>刷新状态</button>
      </div>
      <aside className="privacy-note"><strong>范围说明</strong><p>FDE 可以启停已安装能力，不能通过界面上传任意代码；搜索脱敏确保内部金额、客户名、合同信息和文件正文不会发送到公开搜索接口。</p></aside>
    </div>
  );
}

function AdminRuntime({ data, me, onNotify }: {
  data: AdminBootstrap;
  me: AuthMe;
  onNotify: (message: string) => void;
}) {
  const [auditEvents, setAuditEvents] = useState<AdminAuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [verifying, setVerifying] = useState(false);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    setAuditError("");
    try {
      const result = await adminServices.audit.list(null, { limit: 12 });
      setAuditEvents(result.items);
    } catch (error) {
      setAuditError(humanizeApiError(error));
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => { void loadAudit(); }, [loadAudit]);

  async function downloadReport() {
    const runtime = data.runtime;
    const payload = {
      generated_at: new Date().toISOString(),
      enterprise: me.enterprise.slug,
      app_env: runtime?.app_env ?? null,
      app_mode: runtime?.app_mode ?? null,
      version: runtime?.version ?? null,
      database: runtime?.database ?? null,
      storage: runtime?.storage ?? null,
      demo_data_enabled: runtime?.demo_data_enabled ?? null,
      executive_messages: "excluded",
      recent_audit_actions: auditEvents.slice(0, 12).map((event) => ({
        action: event.action,
        outcome: event.outcome,
        environment: event.environment,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ai-secretary-diagnostic-redacted.json";
    anchor.click();
    URL.revokeObjectURL(url);
    onNotify("脱敏诊断报告已下载");
  }

  async function verifyAudit() {
    setVerifying(true);
    try {
      const result = await adminServices.audit.verify();
      onNotify(
        result.valid
          ? `审计链验证通过（${result.checked_count} 条）`
          : `审计链验证失败（${result.invalid_event_ids.length} 条问题）`,
      );
    } catch (error) {
      onNotify(`验证失败：${humanizeApiError(error)}`);
    } finally {
      setVerifying(false);
    }
  }

  const runtime = data.runtime;
  const runtimeItems: Array<{ label: string; value: string; tone: Tone }> = [
    { label: "应用版本", value: runtime ? `${runtime.app_env} · ${runtime.version}` : "—", tone: runtime ? "positive" : "attention" },
    { label: "当前模式", value: runtime?.app_mode ?? "—", tone: runtime ? "positive" : "attention" },
    { label: "数据库", value: runtime?.database ?? "—", tone: runtime?.database === "healthy" ? "positive" : "risk" },
    { label: "存储", value: runtime?.storage ?? "—", tone: "neutral" },
    { label: "演示数据", value: runtime?.demo_data_enabled ? "启用" : "关闭", tone: runtime?.demo_data_enabled ? "attention" : "positive" },
    { label: "企业", value: me.enterprise.name, tone: "neutral" },
  ];

  return (
    <div className="page subpage admin-page">
      <section className="page-heading split">
        <div>
          <p className="eyebrow">部署版本 {runtime?.version ?? "未知"}</p>
          <h1>运行状态</h1>
          <p>诊断信息不包含完整密钥、Prompt 或高层消息正文。</p>
        </div>
        <div className="heading-actions">
          <button type="button" className="secondary-button" onClick={loadAudit} disabled={auditLoading}>刷新审计</button>
          <button type="button" className="secondary-button" onClick={() => void verifyAudit()} disabled={verifying}>{verifying ? "校验中" : "校验审计链"}</button>
          <button type="button" className="primary-button" onClick={downloadReport}>下载脱敏诊断</button>
        </div>
      </section>
      {data.runtimeError && <p className="form-error">{data.runtimeError}</p>}
      <section className="runtime-grid">
        {runtimeItems.map((item) => (
          <article key={item.label}>
            <small>{item.label}</small>
            <strong>{item.value}</strong>
            <StatusBadge tone={item.tone} label={item.tone === "positive" ? "正常" : item.tone === "risk" ? "需关注" : item.tone === "attention" ? "关注" : "—"} />
          </article>
        ))}
      </section>
      <section className="settings-section">
        <header className="section-header">
          <div><p className="eyebrow">审计摘要</p><h2>最近路由记录</h2></div>
          <span>不含用户消息正文</span>
        </header>
        {auditError && <p className="form-error">{auditError}</p>}
        {auditLoading ? (
          <p className="settings-footnote">正在加载审计事件…</p>
        ) : (
          <div className="simple-list">
            {auditEvents.slice(0, 12).map((event) => (
              <div key={event.id}>
                <time>{formatTimestamp(event.created_at)}</time>
                <span>
                  <strong>{event.action}</strong>
                  <small>{event.actor_role ? `${event.actor_role} · ` : ""}{event.environment}</small>
                </span>
                <StatusBadge tone={toneFromOutcome(event.outcome)} label={event.outcome === "success" ? "成功" : event.outcome === "failure" ? "失败" : event.outcome} />
              </div>
            ))}
            {auditEvents.length === 0 && !auditError && <div><time>—</time><span><strong>暂无审计记录</strong><small>等待后端产生新事件</small></span><StatusBadge tone="neutral" label="—" /></div>}
          </div>
        )}
      </section>
    </div>
  );
}