"use client";

import { useCallback, useEffect, useState } from "react";
import type { AppNotification } from "./types";
import { productionServices } from "./services";

/**
 * 通知铃铛：显示未读计数，点击展开通知列表，可标记已读 / 触发每日摘要。
 *
 * 轻量级组件：不维护全局 store，仅靠自身 state + 轮询（30s）刷新未读数。
 */
export function NotificationBell({ pollIntervalMs = 30_000 }: { pollIntervalMs?: number }) {
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshUnread = useCallback(async () => {
    try {
      const { unread: count } = await productionServices.notifications.unreadCount();
      setUnread(count);
    } catch {
      // 静默失败，不打扰用户
    }
  }, []);

  useEffect(() => {
    void refreshUnread();
    const timer = window.setInterval(refreshUnread, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [refreshUnread, pollIntervalMs]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await productionServices.notifications.list({ limit: 20 });
      setItems(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载通知失败");
    } finally {
      setLoading(false);
    }
  }, []);

  function handleToggle() {
    const next = !open;
    setOpen(next);
    if (next && items.length === 0) {
      void loadItems();
    }
  }

  async function handleMarkAllRead() {
    try {
      await productionServices.notifications.markRead({ all: true });
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "标记已读失败");
    }
  }

  async function handleGenerateDigest() {
    try {
      await productionServices.notifications.generateDigest();
      setError(null);
      // 提示已入队（简单 alert，避免引入额外 UI）
      window.alert("已触发每日邮件摘要生成，稍后将通过通知中心推送。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "触发摘要失败");
    }
  }

  return (
    <div className="notification-bell">
      <button
        type="button"
        className="notification-bell-trigger"
        aria-label={`通知（${unread} 条未读）`}
        aria-expanded={open}
        onClick={handleToggle}
      >
        <span aria-hidden="true">🔔</span>
        {unread > 0 && (
          <span className="notification-bell-badge" aria-hidden="true">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="notification-bell-panel" role="dialog" aria-label="站内通知">
          <div className="notification-bell-header">
            <strong>通知</strong>
            <div className="notification-bell-actions">
              <button type="button" onClick={handleGenerateDigest} disabled={loading}>
                生成今日摘要
              </button>
              {unread > 0 && (
                <button type="button" onClick={handleMarkAllRead} disabled={loading}>
                  全部已读
                </button>
              )}
              <button type="button" onClick={() => setOpen(false)} aria-label="关闭">
                ✕
              </button>
            </div>
          </div>
          {error && <div className="notification-bell-error">{error}</div>}
          <ul className="notification-bell-list">
            {loading && items.length === 0 && <li className="notification-bell-empty">加载中…</li>}
            {!loading && items.length === 0 && (
              <li className="notification-bell-empty">暂无通知</li>
            )}
            {items.map((n) => (
              <li
                key={n.id}
                className={`notification-bell-item${n.is_read ? "" : " unread"}`}
                data-importance={n.importance}
              >
                <div className="notification-bell-item-title">
                  {n.importance === "high" && <span aria-hidden="true">⚠</span>}
                  {n.title}
                </div>
                {n.body && <p className="notification-bell-item-body">{n.body}</p>}
                <time className="notification-bell-item-time" dateTime={n.created_at}>
                  {formatRelative(n.created_at)}
                </time>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function formatRelative(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return "刚刚";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`;
  if (diffSec < 7 * 86400) return `${Math.floor(diffSec / 86400)} 天前`;
  return new Date(iso).toLocaleDateString();
}
