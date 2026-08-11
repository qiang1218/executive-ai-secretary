/**
 * 把 "执行进度" 阶段步骤下产生的中间文本（interim_assistant、thinking 的展开说明等）
 * 与它对应的 stage 关联起来，并以 sessionStorage 持久化。
 *
 * 设计目标：
 *   - 后端不需要持久化这些中间评论。
 *   - 仅在当前会话窗口有效：刷新后 sessionStorage 仍可恢复，
 *     关闭浏览器后清空。
 *   - 不依赖后端协议变化：数据来源 = 流式产出的 tool_steps + message.content。
 *
 * 注意：本 hook 只读不写。写入由 AssistantMessageBody 内部根据 props 决定。
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import type { ToolStep } from "./types";

const STORAGE_PREFIX = "exec-stages:";
const STORAGE_VERSION = 1;

export type StoredEnvelope = {
  version: number;
  conversationId: string;
  messageId: string;
  /** key = stage 标识（序号 + stageKind + name），value = 该阶段下挂的 markdown 输出 */
  stageOutputs: Record<string, string>;
  /** 没有 envelope 时，整段 message.content 视为最终输出；保留用于"无 envelope"分支 */
  conclusionHtml: string;
  updatedAt: string;
};

function storageKey(conversationId: string, messageId: string): string {
  return `${STORAGE_PREFIX}${conversationId}:${messageId}`;
}

function safeRead(raw: string | null): StoredEnvelope | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredEnvelope;
    if (parsed.version !== STORAGE_VERSION) return null;
    if (!parsed.stageOutputs || typeof parsed.stageOutputs !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

function safeWrite(key: string, value: StoredEnvelope): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // 忽略：私密模式或配额限制不影响渲染
  }
}

/**
 * 根据 tool_steps 计算一个稳定的 stage 标识。
 * 同名 step + 同 stageKind + 同在数组里出现的相对序号，方便"刷新后还能对齐"。
 */
export function stageKey(step: ToolStep, index: number): string {
  const kind = step.stageKind ?? (step.kind ?? "tool");
  return `${index}:${kind}:${step.name}`;
}

export function useStageOutputs(
  conversationId: string | undefined,
  messageId: string | undefined,
  steps: ToolStep[] | undefined,
  fallbackConclusion: string,
) {
  const key = conversationId && messageId ? storageKey(conversationId, messageId) : null;
  const initial = useMemo<StoredEnvelope | null>(() => {
    if (typeof window === "undefined" || !key) return null;
    return safeRead(window.sessionStorage.getItem(key));
  }, [key]);

  const [stageOutputs, setStageOutputs] = useState<Record<string, string>>(initial?.stageOutputs ?? {});
  const [conclusionHtml, setConclusionHtml] = useState<string>(initial?.conclusionHtml ?? "");

  // 首次挂载/会话切换时，按 key 重新读取
  useEffect(() => {
    if (!key) return;
    const stored = safeRead(window.sessionStorage.getItem(key));
    if (stored) {
      setStageOutputs(stored.stageOutputs);
      setConclusionHtml(stored.conclusionHtml);
    }
  }, [key]);

  function persist(nextStages: Record<string, string>, nextConclusion: string) {
    if (!key || !conversationId || !messageId) return;
    const envelope: StoredEnvelope = {
      version: STORAGE_VERSION,
      conversationId,
      messageId,
      stageOutputs: nextStages,
      conclusionHtml: nextConclusion,
      updatedAt: new Date().toISOString(),
    };
    safeWrite(key, envelope);
  }

  function setOutputForStage(step: ToolStep, index: number, html: string) {
    const k = stageKey(step, index);
    setStageOutputs((prev) => {
      const next = { ...prev, [k]: html };
      persist(next, conclusionHtml);
      return next;
    });
  }

  function setConclusion(html: string) {
    setConclusionHtml(html);
    persist(stageOutputs, html);
  }

  return {
    stageOutputs,
    conclusionHtml,
    setOutputForStage,
    setConclusion,
    /** 用于"刷新后第一次进来"使用的兜底（即没有缓存时） */
    hasStored: Boolean(initial),
    stepsCount: steps?.length ?? 0,
  };
}
