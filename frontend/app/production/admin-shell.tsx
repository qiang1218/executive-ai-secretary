"use client";

import { useEffect, useState } from "react";
import type { AuthMe } from "./types";
import { type AdminView } from "./admin-shell-types";
import { AdminGuide, ModelProviderPanel, McpToolsPanel, McpSchemaPanel } from "./admin-shell-views";
import { DataOperationsPanel, HarnessPolicyPanel } from "./admin-shell-views-data";

export function ProductionAdmin({
  me,
  onLogout,
}: {
  me: AuthMe;
  onLogout: () => void;
}) {
  const [view, setView] = useState<AdminView>("models");
  const [guideCollapsed, setGuideCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("executive-admin-guide-collapsed") === "true";
  });

  useEffect(() => {
    const saved = window.localStorage.getItem("executive-workbench-theme");
    const theme = saved === "light" || saved === "dark" || saved === "system" ? saved : "system";
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme === "system" ? "light dark" : theme;
    if (!saved) window.localStorage.setItem("executive-workbench-theme", "system");
  }, []);

  function toggleGuide() {
    setGuideCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("executive-admin-guide-collapsed", String(next));
      return next;
    });
  }

  const panel = view === "models"
    ? <ModelProviderPanel />
    : view === "harness"
      ? <HarnessPolicyPanel />
      : view === "mcp"
        ? <McpToolsPanel />
      : view === "mcp_schema"
        ? <McpSchemaPanel />
        : <DataOperationsPanel />;

  return (
    <div className="production-admin-shell" data-app-mode={me.app_mode} data-app-environment={me.app_env}>
      <aside className="production-admin-rail">
        <div className="production-admin-brand"><span aria-hidden="true">董</span><div><strong>AI 秘书管理端</strong><small>{me.enterprise.name}</small></div></div>
        <nav aria-label="管理功能">
          <button className={view === "models" ? "active" : ""} type="button" onClick={() => setView("models")}><span aria-hidden="true">模</span><strong>模型服务</strong></button>
          <button className={view === "harness" ? "active" : ""} type="button" onClick={() => setView("harness")}><span aria-hidden="true">编</span><strong>编排策略</strong></button>
          <button className={view === "mcp" ? "active" : ""} type="button" onClick={() => setView("mcp")}><span aria-hidden="true">工</span><strong>MCP 工具</strong></button>
          <button className={view === "mcp_schema" ? "active" : ""} type="button" onClick={() => setView("mcp_schema")}><span aria-hidden="true">表</span><strong>数据 Schema</strong></button>
          <button className={view === "data" ? "active" : ""} type="button" onClick={() => setView("data")}><span aria-hidden="true">数</span><strong>经营数据</strong></button>
        </nav>
        <div className="production-admin-account"><span aria-hidden="true">{me.user.display_name.slice(0, 1)}</span><div><strong>{me.user.display_name}</strong><small>{me.user.role === "fde" ? "实施与运维" : "企业管理员"}</small></div><button type="button" onClick={onLogout}>退出</button></div>
      </aside>
      <div className={`production-admin-stage${guideCollapsed ? " guide-collapsed" : ""}`}>
        {panel}
        <AdminGuide view={view} collapsed={guideCollapsed} onToggle={toggleGuide} />
      </div>
    </div>
  );
}
