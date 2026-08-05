"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { Conversation, OrganizationUnit, Project } from "./types";
import { UiIcon } from "./ui-icon";
import {
  ALL_SCOPE_ID,
  type ConfirmState,
  type ProjectDialogState,
} from "./workspace-types";

export function ProjectDialog({
  state,
  project,
  organizationUnits,
  onClose,
  onSave,
}: {
  state: ProjectDialogState;
  project: Project | null;
  organizationUnits: OrganizationUnit[];
  onClose: () => void;
  onSave: (name: string, description: string, organizationUnitId: string) => Promise<boolean>;
}) {
  const [name, setName] = useState(project?.name ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [organizationUnitId, setOrganizationUnitId] = useState(project?.organization_unit_id ?? ALL_SCOPE_ID);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);
  const editing = state.mode === "edit";

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLInputElement>("input")?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", handleKeyDown); previouslyFocused?.focus(); };
  }, [onClose]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) { setError("请输入项目名称。"); return; }
    setSubmitting(true);
    const saved = await onSave(name.trim(), description.trim(), organizationUnitId);
    setSubmitting(false);
    if (!saved) setError("项目暂时未能保存，请检查页面提示后重试。");
  }

  return (
    <div className="project-dialog-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="project-dialog" role="dialog" aria-modal="true" aria-labelledby="production-project-dialog-title">
        <header><div><small>{editing ? "项目设置" : "工作项目"}</small><h2 id="production-project-dialog-title">{editing ? "编辑项目" : "创建项目"}</h2></div><button type="button" aria-label="关闭项目窗口" onClick={onClose}>×</button></header>
        <form onSubmit={submit}>
          <label className="project-name-field"><span>项目名称</span><span className="project-name-input"><UiIcon name="folder" /><input value={name} maxLength={200} onChange={(event) => { setName(event.target.value); setError(""); }} placeholder="例如：年度经营计划" autoComplete="off" /></span></label>
          <label className="project-description-field"><span>项目说明 <small>可选</small></span><textarea value={description} maxLength={4000} rows={3} onChange={(event) => setDescription(event.target.value)} placeholder="说明该项目持续关注的经营主题或范围" /><small>创建后，可直接从项目中开始一条新会话。</small></label>
          <label className="project-scope-field"><span>默认事业部范围</span><select value={organizationUnitId} onChange={(event) => setOrganizationUnitId(event.target.value)}><option value={ALL_SCOPE_ID}>全部授权事业部</option>{organizationUnits.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select><small>可选项来自企业管理员配置，不会扩大账号权限。</small></label>
          {error && <p className="project-dialog-error" role="alert">{error}</p>}
          <footer><button type="button" className="secondary-button" onClick={onClose}>取消</button><button type="submit" className="primary-button" disabled={!name.trim() || submitting}>{submitting ? "保存中…" : editing ? "保存修改" : "创建项目"}</button></footer>
        </form>
      </section>
    </div>
  );
}

export function ConversationProjectDialog({
  conversation,
  projects,
  onClose,
  onMove,
}: {
  conversation: Conversation | null;
  projects: Project[];
  onClose: () => void;
  onMove: (projectId: string | null) => Promise<boolean>;
}) {
  const [query, setQuery] = useState("");
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const visibleProjects = projects.filter((project) => (
    project.id !== conversation?.project_id
    && project.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
  ));

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLInputElement>("input")?.focus());
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => { window.removeEventListener("keydown", onKeyDown); previouslyFocused?.focus(); };
  }, [onClose]);

  async function move(projectId: string | null) {
    setSubmittingId(projectId ?? "unassigned");
    const moved = await onMove(projectId);
    if (!moved) setSubmittingId(null);
  }

  return (
    <div className="project-dialog-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="project-dialog conversation-project-dialog" role="dialog" aria-modal="true" aria-labelledby="conversation-project-dialog-title">
        <header><div><small>会话归属</small><h2 id="conversation-project-dialog-title">移到项目</h2></div><button type="button" aria-label="关闭" onClick={onClose}>×</button></header>
        <div className="conversation-project-dialog-body">
          <p>“{conversation?.title || "未命名会话"}”一次只归属一个项目，历史消息、模型和证据不会改变。</p>
          <label><span className="sr-only">搜索项目</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目" /></label>
          <div className="conversation-project-options">
            {conversation?.project_id && <button type="button" disabled={Boolean(submittingId)} onClick={() => void move(null)}><UiIcon name="remove" /><span><strong>移出项目</strong><small>回到最近会话</small></span>{submittingId === "unassigned" && <i>处理中…</i>}</button>}
            {visibleProjects.map((project) => <button type="button" key={project.id} disabled={Boolean(submittingId)} onClick={() => void move(project.id)}><UiIcon name="folder" /><span><strong>{project.name}</strong><small>{project.description || "项目会话"}</small></span>{submittingId === project.id && <i>处理中…</i>}</button>)}
            {!visibleProjects.length && !conversation?.project_id && <small className="conversation-project-empty">没有可移动的项目。</small>}
          </div>
        </div>
        <footer><button type="button" className="secondary-button" onClick={onClose}>取消</button></footer>
      </section>
    </div>
  );
}

export function ConfirmDialog({ state, onCancel, onConfirm }: { state: ConfirmState; onCancel: () => void; onConfirm: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onCancel(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLButtonElement>("button:not([disabled])"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => { window.removeEventListener("keydown", handleKeyDown); previouslyFocused?.focus(); };
  }, [onCancel]);
  return <div className="overlay dialog-overlay" role="presentation"><section ref={dialogRef} className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="production-confirm-title"><span className={`confirm-mark ${state.tone === "danger" ? "danger" : ""}`} aria-hidden="true">!</span><h2 id="production-confirm-title">{state.title}</h2><p>{state.description}</p><div><button type="button" className="secondary-button" onClick={onCancel}>取消</button><button type="button" className={state.tone === "danger" ? "danger-button" : "primary-button"} onClick={onConfirm}>{state.confirmLabel}</button></div></section></div>;
}

export function EmptyState({ title, description, action, onAction }: { title: string; description: string; action?: string; onAction?: () => void }) {
  return <section className="empty-state"><span aria-hidden="true">∅</span><h2>{title}</h2><p>{description}</p>{action && onAction && <button type="button" className="secondary-button" onClick={onAction}>{action}</button>}</section>;
}

export function Toast({ message }: { message: string }) {
  return <div className="toast" role="status" aria-live="polite"><span className="status-dot positive" aria-hidden="true" />{message}</div>;
}
