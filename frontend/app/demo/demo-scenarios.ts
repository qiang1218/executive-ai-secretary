/**
 * 演示抽屉 — 一键跑场景,推屏预览,30 秒锁定。
 *
 * 参考 ``new/app/page.tsx`` 的 ``demoScenarios`` / ``DemoDrawer`` / ``FeishuPreview`` /
 * 30 秒锁定逻辑;**以本项目 demo 模式实现为准**。
 */

export type DemoScenario = {
  id: string;
  title: string;
  description: string;
  prompt: string;
  expectedAnswer: "data_answer" | "executive_pulse" | "forecast_delta" | "operational_pulse" | "general_answer";
  durationMs: number;
};

export const DEMO_SCENARIOS: ReadonlyArray<DemoScenario> = [
  {
    id: "scenario_cash_overdue",
    title: "本周现金流逾期",
    description: "立刻给出本周现金流逾期笔数与金额,按事业部分组。",
    prompt: "请拉出本周现金流逾期清单,按事业部分组。",
    expectedAnswer: "operational_pulse",
    durationMs: 4200,
  },
  {
    id: "scenario_revenue_trend",
    title: "近 90 天营收趋势",
    description: "输出近 90 天营收 trends + 同比/环比。",
    prompt: "近 90 天营收趋势怎样?",
    expectedAnswer: "data_answer",
    durationMs: 4800,
  },
  {
    id: "scenario_forecast_delta",
    title: "Q3 商机预测偏差",
    description: "对比 Q3 商机预测与实际,给出偏差最大的 5 个客户。",
    prompt: "Q3 商机预测与实际偏差最大的 5 个客户是哪些?",
    expectedAnswer: "forecast_delta",
    durationMs: 4600,
  },
  {
    id: "scenario_daily_pulse",
    title: "今日高层经营摘要",
    description: "5 张总结卡 + 3 条建议 + 警示信号。",
    prompt: "给我今天的高层经营摘要。",
    expectedAnswer: "executive_pulse",
    durationMs: 3600,
  },
];

export const DEMO_LOCK_SECONDS = 30;

export function buildFeishuPreviewMessage(period: "daily" | "weekly"): string {
  if (period === "daily") {
    return [
      "📊 今日高层经营摘要",
      "营收 1,234 万 (+12.4% 同比 / +3.1% 环比)",
      "项目交付 7 个,其中 1 个健康度黄灯",
      "逾期 4 笔,合计 320 万",
      "处置建议: 重点跟进健康度黄灯项目",
    ].join("\n");
  }
  return [
    "📈 本周高层简报",
    "营收 6,540 万 (+8.2% 同比)",
    "新增商机 36 个,赢率 38%",
    "回款 4,210 万,回款率 64%",
    "下周关注: 行业 A 客户续约",
  ].join("\n");
}
