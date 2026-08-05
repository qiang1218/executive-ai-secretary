import type {
  AuthMe,
  Conversation,
  ConversationMessage,
  DataCapabilities,
  DailyBrief,
  OrganizationScope,
  OrganizationUnit,
} from "./types";
import { copy, type UiLanguage } from "./workspace-types";

export function preferredDisplayName(me: AuthMe) {
  return me.user.preferred_name || me.user.display_name || me.user.email;
}

export function environmentLabel(me: AuthMe) {
  return me.app_env === "local-demo" || me.app_mode === "demo"
    ? "脱敏演示环境"
    : "生产环境";
}

export function localizedDate(locale: string, timezone: string) {
  try {
    const resolvedLocale = locale || "zh-CN";
    const formatter = new Intl.DateTimeFormat(resolvedLocale, {
      year: "numeric",
      month: "numeric",
      day: "numeric",
      weekday: "long",
      timeZone: timezone || "Asia/Shanghai",
    });
    if (!resolvedLocale.startsWith("zh")) return formatter.format(new Date());
    const values = Object.fromEntries(
      formatter.formatToParts(new Date()).map((part) => [part.type, part.value]),
    );
    return `${values.year}年${values.month}月${values.day}日，${values.weekday}`;
  } catch {
    return new Intl.DateTimeFormat("zh-CN", { dateStyle: "full" }).format(new Date());
  }
}

export function formatTimestamp(value: string | null | undefined, locale: string = "zh-CN") {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatDate(value: string, locale: string = "zh-CN") {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }).format(date);
}

export function dailyBriefDataAsOf(brief: DailyBrief | null) {
  return brief?.data_as_of ?? null;
}

export function dailyBriefHeadline(brief: DailyBrief, language: UiLanguage) {
  const uncertain = brief.readiness === "partial" || brief.readiness === "unavailable";
  if (language === "en") {
    if (uncertain && brief.attention_count === 0) return "There is not enough current data to make a determination";
    if (uncertain) return `${brief.attention_count} item${brief.attention_count === 1 ? "" : "s"} identified for confirmation so far`;
    return brief.attention_count > 0
      ? `${brief.attention_count} item${brief.attention_count === 1 ? "" : "s"} need your attention today`
      : "Nothing needs your confirmation today";
  }
  if (language === "zh-TW") {
    if (uncertain && brief.attention_count === 0) return "目前數據不足，暫不能判斷";
    if (uncertain) return `目前已識別 ${brief.attention_count} 項需要確認`;
    return brief.attention_count > 0
      ? `今日有 ${brief.attention_count} 項需要確認`
      : "今日暫無需要確認的事項";
  }
  if (uncertain && brief.attention_count === 0) return "当前数据不足，暂不能判断";
  if (uncertain) return `当前已识别 ${brief.attention_count} 项需要确认`;
  return brief.attention_count > 0
    ? `今日有 ${brief.attention_count} 项需要确认`
    : "今日暂无需要确认的事项";
}

export const domainLabels: Record<string, string> = {
  opportunity: "商机",
  delivery: "交付",
  collection: "回款",
  target: "目标",
};

export function professionalSourceLabel(value: string | null | undefined) {
  if (!value) return "经营数据源";
  return value
    .replaceAll("飞书经营三表", "飞书经营数据源")
    .replaceAll("飞书三表", "飞书经营数据源")
    .replaceAll("三表批次", "经营数据批次");
}

export function dataStatusLabel(capabilities: DataCapabilities | null) {
  if (!capabilities) return "数据状态待确认";
  if (capabilities.overall_status === "fresh") return "经营数据已就绪";
  if (capabilities.overall_status === "stale") return "部分数据时间较早";
  if (capabilities.overall_status === "partial") return "部分数据可用";
  if (capabilities.overall_status === "failed") return "数据同步失败";
  return "尚未完成数据同步";
}

export function messageStatusLabel(status: ConversationMessage["status"]) {
  if (status === "queued") return "等待受控处理";
  if (status === "running") return "正在处理";
  if (status === "failed") return "未完成";
  if (status === "completed") return "已完成";
  return status ?? "";
}

export function makeInitials(value: string) {
  const normalized = value.trim();
  if (!normalized) return "董";
  const latin = normalized
    .split(/[\s._-]+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2);
  return latin || normalized.slice(0, 2);
}

export function sortByPinnedAndRecent<T extends { pinned_at: string | null; updated_at: string }>(items: T[]) {
  return [...items].sort((first, second) => {
    if (Boolean(first.pinned_at) !== Boolean(second.pinned_at)) return first.pinned_at ? -1 : 1;
    return second.updated_at.localeCompare(first.updated_at);
  });
}

export function scopeLabel(scope: OrganizationScope, units: OrganizationUnit[], language: UiLanguage) {
  const c = copy[language];
  if (scope.mode === "all_authorized") return c.scope;
  const names = scope.organization_unit_ids
    .map((id) => units.find((unit) => unit.id === id)?.name)
    .filter((name): name is string => Boolean(name));
  if (names.length === 1) return names[0];
  if (names.length === 2) return names.join("、");
  return language === "en" ? `${names.length} business units selected` : `已选 ${names.length} 个事业部`;
}

export function scopeFromConversation(conversation: Conversation): OrganizationScope {
  const existing = conversation.organization_scope;
  if (existing) {
    return {
      mode: existing.mode,
      organization_unit_ids: [...existing.organization_unit_ids],
    };
  }
  if (conversation.organization_unit_id) {
    return {
      mode: "selected",
      organization_unit_ids: [conversation.organization_unit_id],
    };
  }
  return {
    mode: "all_authorized",
    organization_unit_ids: [],
  };
}

export function organizationScopeKey(scope: OrganizationScope) {
  return scope.mode === "all_authorized"
    ? "all_authorized"
    : [...scope.organization_unit_ids].sort().join(",");
}

export function resolvedDailyBriefScopeKey(brief: DailyBrief | null) {
  if (!brief) return "all_authorized";
  return brief.uses_enterprise_snapshot
    ? "all_authorized"
    : [...brief.organization_unit_ids].sort().join(",");
}

export function humanizeMetricKey(key: string) {
  const labels: Record<string, string> = {
    opportunity_count: "商机数量",
    pipeline_amount: "商机金额",
    weighted_pipeline_amount: "加权商机",
    delivery_count: "交付项目",
    delivery_attention_count: "交付关注",
    receivable_amount: "应收金额",
    collected_amount: "已回款",
    outstanding_amount: "未回款",
    overdue_amount: "逾期金额",
    weighted_forecast: "加权预测",
    project_count: "项目数量",
    attention_count: "关注项目",
    contract_amount: "合同金额",
    gross_profit_amount: "毛利金额",
    gross_margin_rate: "毛利率",
    name: "名称",
    stage: "阶段",
    bucket: "账龄",
    organization_name: "事业部",
    customer_alias: "客户",
    status: "状态",
    risk_level: "风险等级",
    milestone: "当前里程碑",
    delay_days: "延期天数",
    count: "数量",
    probability: "赢单概率",
    progress_rate: "完成进度",
    target_value: "目标值",
    actual_value: "实际值",
    completion_rate: "完成率",
  };
  return labels[key] ?? key.replaceAll("_", " ");
}

export function formatStructuredValue(key: string, value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value !== "number") {
    if (typeof value !== "string") return "—";
    const valueLabels: Record<string, string> = {
      active: "推进中", stalled: "停滞", won: "已赢单", lost: "已输单", paused: "已暂停",
      normal: "正常", attention: "需关注", delayed: "已延期", critical: "严重风险", high: "高风险",
      completed: "已完成", pending: "待处理", in_progress: "进行中",
    };
    return valueLabels[value] ?? value;
  }
  if (key.endsWith("_rate") || key === "probability") return `${(value * (value <= 1 ? 100 : 1)).toFixed(1)}%`;
  if (key === "delay_days") return `${value.toLocaleString("zh-CN")} 天`;
  if (key.includes("amount") || key.includes("forecast")) {
    return `${(value / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 1 })} 万`;
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

const structuredRowKeys = [
  "organizations",
  "organization_units",
  "metrics",
  "stages",
  "customers",
  "projects",
  "aging",
  "snapshots",
  "rows",
  "items",
];

export function findStructuredRows(value: unknown, depth = 0): unknown[] | null {
  if (!value || depth > 4) return null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const nested = findStructuredRows(item, depth + 1);
      if (nested) return nested;
    }
    return null;
  }
  if (typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  for (const key of structuredRowKeys) {
    const candidate = record[key];
    if (Array.isArray(candidate) && candidate.length > 0) return candidate;
  }
  for (const candidate of Object.values(record)) {
    const nested = findStructuredRows(candidate, depth + 1);
    if (nested) return nested;
  }
  return null;
}

export function visibleStructuredEntries(record: Record<string, unknown>) {
  return Object.entries(record)
    .filter(([key, value]) => (
      !key.includes("source_record_id")
      && !key.endsWith("_id")
      && (typeof value === "string" || typeof value === "number" || typeof value === "boolean")
    ))
    .slice(0, 4);
}

export type StructuredChartDatum = {
  label: string;
  value: number;
};

export function buildStructuredChart(rows: unknown[]) {
  const records = rows.filter(
    (row): row is Record<string, unknown> => Boolean(row && typeof row === "object" && !Array.isArray(row)),
  );
  if (records.length < 2) return null;
  const first = records[0];
  const visibleKeys = Object.keys(first).filter(
    (key) => !key.includes("source_record_id") && !key.endsWith("_id"),
  );
  const labelPriority = ["name", "stage", "bucket", "organization_name", "customer_alias", "risk_level", "status", "period"];
  const labelKey = labelPriority.find((key) => typeof first[key] === "string")
    ?? visibleKeys.find((key) => typeof first[key] === "string");
  const numericKeys = visibleKeys.filter((key) => typeof first[key] === "number");
  const metricKey = numericKeys.sort((left, right) => {
    const score = (key: string) => key.includes("amount") || key.includes("forecast")
      ? 4
      : key.includes("count")
        ? 3
        : key.includes("rate") || key.includes("probability")
          ? 2
          : 1;
    return score(right) - score(left);
  })[0];
  if (!labelKey || !metricKey) return null;
  const items: StructuredChartDatum[] = records
    .map((record) => ({ label: String(record[labelKey] ?? "—"), value: Number(record[metricKey]) }))
    .filter((item) => Number.isFinite(item.value))
    .slice(0, 8);
  if (items.length < 2) return null;
  return { metricKey, items };
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function firstText(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

export function recordItems(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) return value.map(asRecord).filter((item): item is Record<string, unknown> => Boolean(item));
  }
  return [];
}
