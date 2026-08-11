/**
 * 极简 Markdown -> HTML 渲染器（前端、零依赖）。
 *
 * 适用场景：
 *   - "执行进度" 阶段步骤下挂载的中间助理评论/补充文字
 *   - 没有 AssistantOutputEnvelope 时，assistant 消息正文落到 answer-conclusion
 *
 * 支持的子集（足够展示阶段内的过程性内容）：
 *   - 标题：## H2、### H3、#### H4
 *   - 加粗：**bold**
 *   - 行内代码：`code`
 *   - 链接：[label](url)  （生产用，只做安全转义，不解析外链真正跳转；href 仍保留）
 *   - 段落：被空行分隔的文本块
 *   - 无序列表：- / * 开头的行，连续多行累积
 *   - 有序列表：1. 2. 开头的行
 *   - GFM 表格：含 |xx|yy| 行 + 分隔行 |---:|:---:|（缺分行时退化为段落）
 *
 * 不支持（按设计刻意省略，避免歧义或扩展面过广）：
 *   - 代码块（```）。
 *     阶段中间评论几乎不会出现整段代码块；如需，请后端走 AssistantOutputEnvelope。
 *   - 图片引用 ![](url)。
 *   - 任务列表、删除线、脚注、引用块、HTML 内嵌等。
 *
 * 安全：
 *   - 任何用户/模型原文都先经过 escapeHtml 再放入结构化节点，因此
 *     不会因模型产生的 <script>、onerror、javascript: 等触发 XSS。
 *   - 链接协议仅允许 http(s) / mailto，其它（含 javascript: / data:）一律剥除 href。
 */

export function escapeHtml(input: string): string {
  return input
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeHref(href: string): string | null {
  const trimmed = href.trim();
  if (!trimmed) return null;
  if (/^(https?:|mailto:)/i.test(trimmed)) return escapeHtml(trimmed);
  return null;
}

/**
 * 行内元素解析：加粗、行内代码、链接、单元格内的硬换行。
 * 仅产出 HTML 字符串，已转义。
 *
 * 硬换行：表格 cell 内的真实 \n 会被渲染成 <br>，否则单元格里
 * 的多行说明（"阿特斯阳光电力\n财务AI场景沟通"）会挤成一行，视觉错位。
 */
function renderInline(text: string): string {
  let escaped = escapeHtml(text);

  // 行内代码 `` ` `` —— 优先于其他解析，避免内部文本再被处理。
  escaped = escaped.replace(/`([^`\n]+)`/g, (_match, inner: string) => `<code>${inner}</code>`);

  // 链接 [label](url)
  escaped = escaped.replace(/\[([^\]\n]+)\]\(([^)\n]+)\)/g, (_match, label: string, href: string) => {
    const safe = safeHref(href);
    if (!safe) return escapeHtml(label);
    return `<a href="${safe}" rel="noopener noreferrer" target="_blank">${label}</a>`;
  });

  // 加粗 **text**
  escaped = escaped.replace(/\*\*([^*\n]+)\*\*/g, (_match, inner: string) => `<strong>${inner}</strong>`);

  // 真实换行 → <br>。位置在所有内联解析之后，避免误伤其他正则。
  escaped = escaped.replace(/\n/g, "<br>");

  return escaped;
}

/**
 * 渲染 Markdown 字符串为安全 HTML。
 * 输入：原始 markdown 文本
 * 输出：可直接通过 dangerouslySetInnerHTML 注入的 HTML 字符串
 */
export function renderMarkdownToHtml(input: string | null | undefined): string {
  if (!input) return "";
  const lines = input.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // 表格：要求 |col|col| ... 行 + 分隔行
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const headerCells = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
      i += 2; // 跳过分隔行
      const rows: string[][] = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        const cells = lines[i].trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
        rows.push(cells);
        i += 1;
      }
      const thead = `<thead><tr>${headerCells.map((c) => `<th>${renderInline(c)}</th>`).join("")}</tr></thead>`;
      const tbody = `<tbody>${rows
        .map((row) => `<tr>${row.map((c) => `<td><div class="md-cell">${renderInline(c)}</div></td>`).join("")}</tr>`)
        .join("")}</tbody>`;
      out.push(`<table>${thead}${tbody}</table>`);
      continue;
    }

    // 标题
    const headingMatch = /^(#{2,4})\s+(.+?)\s*$/.exec(line);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      out.push(`<h${level}>${renderInline(text)}</h${level}>`);
      i += 1;
      continue;
    }

    // 无序列表
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        const item = lines[i].replace(/^\s*[-*]\s+/, "");
        items.push(`<li>${renderInline(item)}</li>`);
        i += 1;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    // 有序列表
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        const item = lines[i].replace(/^\s*\d+\.\s+/, "");
        items.push(`<li>${renderInline(item)}</li>`);
        i += 1;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    // 空行：跳过（作为段落分隔）
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // 段落：合并相邻非空行
    const paragraph: string[] = [line];
    i += 1;
    while (i < lines.length && lines[i].trim() !== "" && !/^\s*[-*]\s+/.test(lines[i]) && !/^\s*\d+\.\s+/.test(lines[i]) && !/^#{2,4}\s+/.test(lines[i]) && !/^\s*\|.*\|\s*$/.test(lines[i])) {
      paragraph.push(lines[i]);
      i += 1;
    }
    const text = paragraph.join(" ").trim();
    if (text) out.push(`<p>${renderInline(text)}</p>`);
  }

  return out.join("");
}

/**
 * 探测一段文本是否“看起来像 Markdown”。
 * 用于决定是否要走渲染器，还是用纯文本 fallback。
 */
export function looksLikeMarkdown(input: string | null | undefined): boolean {
  if (!input) return false;
  return /(?:^|\n)\s*#{2,4}\s+/.test(input)
    || /(?:^|\n)\s*[-*]\s+\S/.test(input)
    || /(?:^|\n)\s*\d+\.\s+\S/.test(input)
    || /\*\*(?:[^*\n]+)\*\*/.test(input)
    || /`[^`\n]+`/.test(input)
    || /\|[^\n]+\|/.test(input)
    || /\[(?:[^\]\n]+)\]\((?:[^)\n]+)\)/.test(input);
}
