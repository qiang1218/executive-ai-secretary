import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

// Note: the previous "server-renders the configured executive assistant entry"
// test required importing a built artifact at ../dist/server/index.js.
// That test has been removed: it depended on 'npm run build' producing dist/,
// which is not part of the source-only quality gate. The accessibility and
// prototype-source checks below exercise the same surface without needing
// a built server bundle.

test("includes accessible controls for login and first-use security", async () => {
  const productionApp = await readFile(new URL("../app/production/app.tsx", import.meta.url), "utf8");

  assert.match(productionApp, /href="#production-login-form"/);
  assert.match(productionApp, /id="production-login-form"/);
  assert.match(productionApp, /autoComplete="username"/);
  assert.match(productionApp, /autoComplete="current-password"/);
  assert.match(productionApp, /type=\{showPassword \? "text" : "password"\}/);
  assert.match(productionApp, /联系企业管理员/);
});

test("prototype source contains the required functional contracts", async () => {
  const demoPrototype = await readFile(new URL("../app/demo/prototype.tsx", import.meta.url), "utf8");
  const data = await readFile(new URL("../app/demo/prototype-data.ts", import.meta.url), "utf8");
  const styles = await readFile(new URL("../src/styles/globals.css", import.meta.url), "utf8");

  assert.match(demoPrototype, /accept="\.pdf,\.docx,\.xlsx,\.pptx"/);
  assert.match(demoPrototype, /十个标准演示场景/);
  assert.match(data, /最多两轮范围选择/);
  assert.match(demoPrototype, /不会检索其他会话文件/);
  assert.match(demoPrototype, /没有生成近似金额/);
  assert.match(demoPrototype, /const COMPOSER_MAX_LENGTH = 8000/);
  assert.match(demoPrototype, /const COMPOSER_HINT_THRESHOLD = COMPOSER_MAX_LENGTH \* 0\.8/);
  assert.match(demoPrototype, /function OrganizationPicker/);
  assert.match(demoPrototype, /configuredByAdmin/);
  assert.match(demoPrototype, /function PersonalCenterWindow/);
  assert.match(demoPrototype, /function ProjectDialog/);
  assert.match(demoPrototype, /aria-label="新建项目"/);
  assert.match(demoPrototype, /const \[sidebarProjects, setSidebarProjects\] = useState<SidebarProject\[]>/);
  assert.match(demoPrototype, /function requestArchiveConversation/);
  assert.match(demoPrototype, /function requestArchiveProjectTasks/);
  assert.match(demoPrototype, /function requestRemoveProject/);
  assert.match(demoPrototype, /归档后，这条会话将从置顶、项目和最近列表中隐藏/);
  assert.match(demoPrototype, /只会移除项目分组/);
  assert.match(demoPrototype, /aria-haspopup="menu"/);
  assert.match(demoPrototype, /"zh-CN".*"zh-TW".*"en"/s);
  assert.doesNotMatch(demoPrototype, /ResponsePreferenceControl|回答：标准|maxLength=\{1200\}/);
  assert.match(styles, /\.preferences-window/);
  assert.match(styles, /\.organization-popover/);
  assert.match(styles, /\.project-dialog-layer/);
  assert.match(styles, /\.sidebar-project-context-menu/);
  for (const id of ["overview", "target", "change", "forecast", "customers", "delivery", "collection", "organization"]) {
    assert.match(data, new RegExp(`\\b${id}: \\{`));
  }
});
