/**
 * ChatGPT 网关身份读取 — 公司 ChatGPT 网关返回的真实员工身份。
 *
 * 参考 ``new/app/chatgpt-auth.ts`` 的设计,但**以本项目 backend 实现为准**：
 * 网关路径环境变量 ``CHATGPT_GATEWAY_URL``（默认 ``https://chatgpt.anspire.cn``），
 * 未配置时返回 ``null`` 让 UI 走本地登录。
 *
 * 该模块只在生产模式（``appMode === "production"``）启用；演示模式下 demo 走
 * 演示账号快速登录,绕过网关。
 */

export type ChatGPTUser = {
  email: string;
  displayName: string;
  employeeId: string;
  department: string;
  expiresAt: string;
};

export function getChatGPTGatewayUrl(): string {
  if (typeof process === "undefined") return "";
  return process.env.NEXT_PUBLIC_CHATGPT_GATEWAY_URL ?? "";
}

export function isChatGPTGatewayConfigured(): boolean {
  return getChatGPTGatewayUrl().length > 0;
}

export async function fetchChatGPTUser(): Promise<ChatGPTUser | null> {
  const url = getChatGPTGatewayUrl();
  if (!url) return null;
  if (typeof fetch === "undefined") return null;
  try {
    const response = await fetch(`${url}/api/identity`, {
      credentials: "include",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) return null;
    const user = (await response.json()) as ChatGPTUser;
    if (!user.email || !user.employeeId) return null;
    return user;
  } catch (error) {
    console.warn("ChatGPT gateway identity fetch failed", error);
    return null;
  }
}

export function buildChatGPTLoginUrl(returnTo: string): string {
  const url = getChatGPTGatewayUrl();
  if (!url) return "/auth/login";
  const params = new URLSearchParams({ return_to: returnTo });
  return `${url}/login?${params.toString()}`;
}
