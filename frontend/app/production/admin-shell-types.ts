import type { HarnessBusinessConfig } from "./types";

export type AdminView = "models" | "harness" | "mcp_schema" | "data" | "skills";

export type DataOperationsView = "sources" | "runs" | "schedule" | "quality" | "policy";

export type ExperienceWeightDraft = { high: number; medium: number; low: number; notes: string };

export type HarnessModule = keyof HarnessBusinessConfig["prompts"] | "glossary" | "rules" | "simulate" | "versions";

export const guideContent: Record<AdminView, { eyebrow: string; title: string; summary: string; principles: string[] }> = {
  models: {
    eyebrow: "配置说明",
    title: "模型只负责推理",
    summary: "Anspire 是唯一模型通道。业务数据、权限和工具边界仍由产品服务端控制。",
    principles: ["保存密钥后先测试连接", "只有测试通过的模型才能启用", "停用不会删除已有配置"],
  },
  harness: {
    eyebrow: "编排边界",
    title: "策略可编辑，安全内核不可覆盖",
    summary: "这里决定问题如何理解、改写、规划和回答；每次保存生成独立版本。",
    principles: ["修改只影响新创建的消息任务", "工具白名单和事业部权限不可编辑", "先用问题模拟检查策略变化"],
  },
  mcp_schema: {
    eyebrow: "Schema 说明",
    title: "Agent 自动发现表结构并生成 SQL",
    summary: "MCP v2：Agent 通过 discover → query → execute 三步自动查询数据，无需预定义工具。",
    principles: ["新表默认已注册，可按需停用", "刷新 Schema 同步最新列结构", "Agent 只能查启用表，SQL 受限"],
  },
  data: {
    eyebrow: "运营说明",
    title: "经营数据按完整批次生效",
    summary: "商机、项目与回款必须同时通过字段、关联和金额校验；失败会继续使用上一完整成功批次。",
    principles: ["连接测试只验证只读与结构契约", "可以先校验且不生效", "正式同步只切换完整成功批次"],
  },
  skills: {
    eyebrow: "技能说明",
    title: "企业级技能，所有会话共享",
    summary: "技能（Skill）按企业配置，启用后对所有会话生效；停用后立即从共享目录清除。",
    principles: ["启用时文件释放到共享目录供 Worker 加载", "停用时自动清理磁盘文件", "修改文件后需重新启用才会生效"],
  },
};

export const harnessPromptFields: Array<{ key: keyof HarnessBusinessConfig["prompts"]; label: string; note: string }> = [
  { key: "system", label: "董事长助理基础 Prompt", note: "定义身份、语气与事实边界" },
  { key: "data_answer", label: "经营回答 Prompt", note: "约束结论、数字证据与数据时间" },
  { key: "general_answer", label: "个人泛化回答 Prompt", note: "用于日常分析、写作与思考" },
  { key: "route", label: "意图识别 Prompt", note: "仅在快速规则未命中时使用" },
  { key: "rewrite", label: "查询改写 Prompt", note: "输出固定 QuerySpec" },
  { key: "plan", label: "任务规划 Prompt", note: "仅选择启用的 MCP 工具" },
];

export const harnessModuleGroups: Array<{ label: string; items: Array<{ key: HarnessModule; label: string }> }> = [
  { label: "身份与回答", items: [{ key: "system", label: "基础身份" }, { key: "data_answer", label: "经营回答" }, { key: "general_answer", label: "个人泛化回答" }] },
  { label: "理解与规划", items: [{ key: "route", label: "意图识别" }, { key: "rewrite", label: "查询改写" }, { key: "plan", label: "任务规划" }, { key: "glossary", label: "业务术语表" }] },
  { label: "规则与验证", items: [{ key: "rules", label: "快速规则" }, { key: "simulate", label: "问题模拟与追踪" }, { key: "versions", label: "版本记录" }] },
];

export function formatAdminTime(value: string | null) {
  if (!value) return "尚无记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function syncStatusLabel(status: string) {
  if (status === "completed" || status === "succeeded") return "成功";
  if (status === "validated") return "校验通过";
  if (status === "rejected") return "已拒绝";
  if (status === "failed") return "失败";
  if (status === "running") return "同步中";
  if (status === "queued") return "排队中";
  return status || "未知";
}

export function atomicStatusLabel(status: string) {
  if (status === "activated") return "完整批次已生效";
  if (status === "activating") return "完整批次生效中";
  if (status === "failed") return "批次生效失败";
  if (status === "rejected") return "批次已拒绝";
  if (status === "not_requested") return "仅校验，未生效";
  return status || "等待处理";
}

export function shortHash(value: string | null | undefined) {
  if (!value) return "—";
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

export function fieldTypeLabel(value: number) {
  const labels: Record<number, string> = {
    1: "文本",
    2: "数字",
    3: "单选",
    4: "多选",
    5: "日期",
    11: "人员",
    13: "电话",
    15: "链接",
    17: "附件",
    20: "公式",
    1001: "创建时间",
    1002: "最后更新时间",
  };
  return labels[value] ?? `类型 ${value}`;
}

export function dataSourceDisplayName(value: string) {
  return value
    .replaceAll("飞书经营三表", "飞书经营数据源")
    .replaceAll("飞书三表", "飞书经营数据源");
}

export function dataSourceTypeLabel(value: string) {
  if (value === "feishu_three_table") return "飞书多维表格";
  if (value === "postgres") return "标准 PostgreSQL";
  return value;
}

export function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

export function formatValidationAmount(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (Math.abs(numeric) >= 10000) {
    return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(numeric / 10000)} 万元`;
  }
  return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(numeric)} 元`;
}

export function copyHarnessConfig(config: HarnessBusinessConfig): HarnessBusinessConfig {
  return JSON.parse(JSON.stringify(config)) as HarnessBusinessConfig;
}
