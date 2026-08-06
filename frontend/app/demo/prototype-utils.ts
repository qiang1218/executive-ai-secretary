import type { AnswerConfig, RouteKind, Tone } from "./prototype-data";
import type { DemoFile, UiLanguage } from "./prototype-types";
import { ALL_ORGANIZATIONS_ID, availableOrganizations, workbenchCopy } from "./prototype-constants";

export function organizationLabel(organizationId: string, language: UiLanguage) {
  return availableOrganizations.find((organization) => organization.id === organizationId)?.labels[language] ?? organizationId;
}

export function formatOrganizationSelection(organizationIds: string[], language: UiLanguage, compact = false) {
  if (!organizationIds.length || organizationIds.includes(ALL_ORGANIZATIONS_ID)) {
    return organizationLabel(ALL_ORGANIZATIONS_ID, language);
  }
  if (organizationIds.length === 1) return organizationLabel(organizationIds[0], language);
  return compact
    ? workbenchCopy[language].selectedOrganizations(organizationIds.length)
    : organizationIds.map((organizationId) => organizationLabel(organizationId, language)).join(language === "en" ? ", " : "、");
}

export function toggleOrganizationSelection(current: string[], organizationId: string) {
  if (organizationId === ALL_ORGANIZATIONS_ID) return [ALL_ORGANIZATIONS_ID];
  const withoutAll = current.filter((id) => id !== ALL_ORGANIZATIONS_ID);
  const next = withoutAll.includes(organizationId)
    ? withoutAll.filter((id) => id !== organizationId)
    : [...withoutAll, organizationId];
  return next.length ? next : [ALL_ORGANIZATIONS_ID];
}

export function makeConversationTitle(question: string, answerId: string) {
  const known: Record<string, string> = { overview: "本月整体经营情况", target: "收入目标完成与差距", change: "商机变化原因", forecast: "本季度签约预测", customers: "重点客户经营情况", delivery: "项目交付与回款", collection: "本月回款情况", organization: "组织与负责人表现", people: "负责人商机推进对比", file: "当前文件要点", research: "行业公开研究", general: "经营材料整理", failure: "回款数据查询" };
  return known[answerId] ?? question.slice(0, 20);
}

export function makeTaskTitle(question: string) {
  const normalized = question.trim().replace(/[？?。！!]+$/, "");
  return normalized.length > 24 ? `${normalized.slice(0, 24)}…` : normalized;
}

export function safeRouteSummary(route: RouteKind) {
  if (route === "file") return "当前会话文件，限定本会话附件";
  if (route === "research") return "公开研究，已执行脱敏检查";
  if (route === "general") return "材料整理，不调用企业数字";
  if (route === "failure") return "经营数据，演示同步失败恢复";
  return "经营数据，时间与组织范围已补全";
}

export function toneLabel(tone: Tone) {
  return tone === "positive" ? "改善" : tone === "risk" ? "需关注" : tone === "attention" ? "有变化" : "正常";
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(bytes / 1024, 0.1).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function fileRange(extension: string) {
  if (extension === "pdf") return "12 页，可复制文字";
  if (extension === "docx") return "正文与 3 个表格";
  if (extension === "xlsx") return "4 个工作表，共 286 行";
  if (extension === "pptx") return "18 张幻灯片";
  return "未读取";
}

export function demoReadyFile(): DemoFile {
  return { id: 26072601, name: "重点项目复盘报告.pdf", kind: "PDF", size: "2.8 MB", status: "可使用", uploadedAt: "刚刚", range: "12 页，可复制文字" };
}

export async function copyToClipboard(text: string, notify: (message: string) => void, message: string) {
  try {
    await navigator.clipboard.writeText(text);
    notify(message);
  } catch {
    notify("浏览器未允许复制，请手动选择文本");
  }
}

export function fullAnswerText(answer: AnswerConfig) {
  return [answer.title, answer.summary, ...answer.metrics.map((metric) => `${metric.label}：${metric.value}（${metric.note}）`), ...answer.sections.map((section) => `${section.title}：${section.body}`), `数据截至：${answer.asOf}`, `范围：${answer.scope}`, `口径：${answer.definition}`].join("\n");
}

export function saveChartImage(answer: AnswerConfig, notify: (message: string) => void) {
  if (!answer.chart) return;
  const canvas = document.createElement("canvas");
  canvas.width = 1200; canvas.height = 675;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.fillStyle = "#fbfaf7"; context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#1c211f"; context.font = "600 38px sans-serif"; context.fillText(answer.chart.title, 72, 82);
  context.fillStyle = "#6d7470"; context.font = "22px sans-serif"; context.fillText(`${answer.scope} · 单位 ${answer.chart.unit}`, 72, 122);
  const max = Math.max(...answer.chart.data.map((item) => item.value));
  answer.chart.data.forEach((item, index) => {
    const y = 185 + index * 55; const width = (item.value / max) * 720;
    context.fillStyle = "#e5e8e5"; context.fillRect(240, y, 760, 24);
    context.fillStyle = "#2457d6"; context.fillRect(240, y, width, 24);
    context.fillStyle = "#1c211f"; context.font = "20px sans-serif"; context.fillText(item.label, 72, y + 20); context.fillText(item.display, 1020, y + 20);
  });
  context.fillStyle = "#6d7470"; context.font = "18px sans-serif"; context.fillText(`数据截至 ${answer.asOf} · 演示样本`, 72, 632);
  const anchor = document.createElement("a"); anchor.download = `${answer.id}-chart.png`; anchor.href = canvas.toDataURL("image/png"); anchor.click(); notify("图表图片已保存");
}
