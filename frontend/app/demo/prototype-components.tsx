"use client";

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  ReactNode,
  RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AdminSection,
  AnswerConfig,
  ConversationItem,
  MemoryItem,
  RouteKind,
  Tone,
  adminNavigation,
  dailyChanges,
  demoScenarios,
  homeSuggestions,
} from "./prototype-data";
import type {
  AuthStep,
  ChatStage,
  ConfirmState,
  DemoFile,
  ExecutiveProfile,
  LoginMode,
  PersonalCenterView,
  ProjectDialogState,
  ScopeState,
  SidebarProject,
  ThemePreference,
  UiIconName,
  UiLanguage,
} from "./prototype-types";
import {
  ALL_ORGANIZATIONS_ID,
  COMPOSER_HINT_THRESHOLD,
  COMPOSER_MAX_LENGTH,
  availableOrganizations,
  initialExecutiveProfile,
  initialSidebarProjects,
  languageOptions,
  owners,
  workbenchCopy,
  workspaceNavigation,
} from "./prototype-constants";
import {
  copyToClipboard,
  demoReadyFile,
  fileRange,
  formatFileSize,
  formatOrganizationSelection,
  fullAnswerText,
  makeConversationTitle,
  makeTaskTitle,
  organizationLabel,
  saveChartImage,
  safeRouteSummary,
  toggleOrganizationSelection,
  toneLabel,
} from "./prototype-utils";

export function LoginScreen({
  mode,
  step,
  account,
  password,
  newPassword,
  confirmPassword,
  error,
  locked,
  onModeChange,
  onAccountChange,
  onPasswordChange,
  onNewPasswordChange,
  onConfirmPasswordChange,
  onLogin,
  onChangePassword,
  onBack,
}: {
  mode: LoginMode;
  step: AuthStep;
  account: string;
  password: string;
  newPassword: string;
  confirmPassword: string;
  error: string;
  locked: boolean;
  onModeChange: (mode: LoginMode) => void;
  onAccountChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onConfirmPasswordChange: (value: string) => void;
  onLogin: (event: FormEvent) => void;
  onChangePassword: (event: FormEvent) => void;
  onBack: () => void;
}) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <main className="login-page">
      <a className="skip-link" href="#login-form">跳到登录表单</a>
      <section className="login-context" aria-labelledby="product-title">
        <div className="login-brand">
          <span className="brand-glyph" aria-hidden="true">董</span>
          <span>董事长 AI 秘书</span>
        </div>
        <div className="login-statement">
          <p className="eyebrow">私有化经营工作入口</p>
          <h1 id="product-title">先核对范围，再回答经营问题。</h1>
          <p>企业数字有来源、有时间、有口径。当前原型全部经营数据均为演示样本。</p>
        </div>
        <dl className="login-principles">
          <div><dt>01</dt><dd><strong>经营数据</strong><span>商机、项目、收入、利润与回款</span></dd></div>
          <div><dt>02</dt><dd><strong>当前文件</strong><span>PDF、Word、Excel 与 PowerPoint</span></dd></div>
          <div><dt>03</dt><dd><strong>泛化助理</strong><span>材料整理、写作与公开研究</span></dd></div>
        </dl>
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-mode-switch" aria-label="登录入口">
          <button type="button" className={mode === "executive" ? "active" : ""} onClick={() => onModeChange("executive")}>高层端</button>
          <button type="button" className={mode === "admin" ? "active" : ""} onClick={() => onModeChange("admin")}>管理端</button>
        </div>

        {step === "login" ? (
          <form id="login-form" className="login-form" onSubmit={onLogin}>
            <div className="form-heading">
              <p className="eyebrow">{mode === "executive" ? "高层用户" : "企业管理员与 FDE"}</p>
              <h2 id="login-title">登录</h2>
              <p>{mode === "executive" ? "进入您的经营工作台。" : "配置连接、任务和受控能力。"}</p>
            </div>
            <label className="field">
              <span>账号</span>
              <input value={account} onChange={(event) => onAccountChange(event.target.value)} autoComplete="username" />
            </label>
            <label className="field password-field">
              <span>密码</span>
              <span className="input-with-action">
                <input type={showPassword ? "text" : "password"} value={password} onChange={(event) => onPasswordChange(event.target.value)} autoComplete="current-password" />
                <button type="button" onClick={() => setShowPassword((current) => !current)}>{showPassword ? "隐藏" : "显示"}</button>
              </span>
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-button wide" type="submit" disabled={!account || !password || locked}>登录</button>
            <div className="demo-credential">
              <strong>原型体验账号</strong>
              <span>{mode === "executive" ? "chairman / Demo@2026" : "admin / Admin@2026"}</span>
            </div>
            <p className="contact-note">无法登录时，请联系企业管理员。首版不提供自行注册。</p>
          </form>
        ) : (
          <form id="login-form" className="login-form" onSubmit={onChangePassword}>
            <button type="button" className="back-link" onClick={onBack}>返回登录</button>
            <div className="form-heading">
              <p className="eyebrow">首次登录</p>
              <h2 id="login-title">设置新密码</h2>
              <p>临时密码不能进入业务页面。新密码至少 8 位，并包含字母和数字。</p>
            </div>
            <label className="field">
              <span>新密码</span>
              <input type="password" value={newPassword} onChange={(event) => onNewPasswordChange(event.target.value)} autoComplete="new-password" placeholder="例如：NewPass2026" />
            </label>
            <label className="field">
              <span>再次确认</span>
              <input type="password" value={confirmPassword} onChange={(event) => onConfirmPasswordChange(event.target.value)} autoComplete="new-password" />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-button wide" type="submit" disabled={!newPassword || !confirmPassword}>保存并进入首页</button>
          </form>
        )}
      </section>
    </main>
  );
}

export function HomeView({
  question,
  setQuestion,
  composerRef,
  fileRef,
  onKeyDown,
  onSubmit,
  onFiles,
  onSuggestion,
  onDaily,
  scope,
  language,
  profile,
  onOrganizationsChange,
}: {
  question: string;
  setQuestion: (value: string) => void;
  composerRef: RefObject<HTMLTextAreaElement | null>;
  fileRef: RefObject<HTMLInputElement | null>;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent) => void;
  onFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onSuggestion: (question: string) => void;
  onDaily: () => void;
  scope: ScopeState;
  language: UiLanguage;
  profile: ExecutiveProfile;
  onOrganizationsChange: (organizationIds: string[]) => void;
}) {
  const copy = workbenchCopy[language];
  const greeting = language === "en" ? `${copy.greeting}, ${profile.displayName}` : `${copy.greeting}，${profile.salutation}`;
  return (
    <div className="workspace-home">
      <div className="home-empty-stage">
        <div className="home-empty-inner">
          <button type="button" className="morning-brief-trigger" onClick={onDaily}>
            <span className="morning-brief-dot" aria-hidden="true" />
            <span><strong>{copy.morningTitle}</strong><small>{copy.morningMeta}</small></span>
            <span>{copy.morningAction} <i aria-hidden="true">›</i></span>
          </button>

          <section className="workspace-greeting" aria-labelledby="workspace-greeting-title">
            <p>{copy.date}</p>
            <div className="greeting-title-line">
              <span className="service-mark" aria-hidden="true" />
              <h1 id="workspace-greeting-title">{greeting}</h1>
            </div>
            <span>{copy.greetingQuestion}</span>
          </section>

          <form className="composer workbench-composer home-primary-composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="executive-question">输入经营问题</label>
          <textarea
            ref={composerRef}
            id="executive-question"
            rows={2}
            maxLength={COMPOSER_MAX_LENGTH}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={copy.composerPlaceholder}
          />
          <div className="composer-footer">
            <div className="composer-tools">
              <input ref={fileRef} className="sr-only" type="file" multiple accept=".pdf,.docx,.xlsx,.pptx" onChange={onFiles} id="home-file-input" />
              <button type="button" className="composer-tool-button" onClick={() => fileRef.current?.click()} aria-label="添加文件"><span aria-hidden="true">＋</span><span>{copy.file}</span></button>
              <OrganizationPicker language={language} selectedIds={scope.organizationIds} onApply={onOrganizationsChange} />
            </div>
            <div className="composer-send">
              {question.length >= COMPOSER_HINT_THRESHOLD && <span className="composer-character-count" aria-live="polite">{copy.remainingCharacters(COMPOSER_MAX_LENGTH - question.length)}</span>}
              <button className="composer-submit-button" type="submit" disabled={!question.trim()} aria-label="发送问题">↑</button>
            </div>
          </div>
        </form>

          <section className="prompt-suggestions" aria-labelledby="prompt-suggestions-title">
            <h2 id="prompt-suggestions-title">{copy.startQuestion}</h2>
            <div>{homeSuggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => onSuggestion(suggestion)}><span>{suggestion}</span><small aria-hidden="true">›</small></button>)}</div>
          </section>

          <p className="home-service-note">{copy.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}

export function ChatView({
  question,
  previousQuestion,
  stage,
  route,
  answer,
  answerVersion,
  scope,
  files,
  selectedFile,
  setSelectedFile,
  inheritedNotice,
  newTopicNotice,
  memoryCandidate,
  clarificationRound,
  clarificationOrganizations,
  setClarificationOrganizations,
  clarificationOwner,
  setClarificationOwner,
  draft,
  setDraft,
  fileRef,
  onOpenScope,
  onOrganizationsChange,
  onStop,
  onRetry,
  onConfirmClarification,
  onFiles,
  onDeleteFile,
  onKeyDown,
  onSubmit,
  onSuggestion,
  onNotify,
  onSaveMemory,
  onDismissMemory,
  language,
}: {
  question: string;
  previousQuestion: string;
  stage: ChatStage;
  route: RouteKind;
  answer: AnswerConfig;
  answerVersion: number;
  scope: ScopeState;
  files: DemoFile[];
  selectedFile: number | null;
  setSelectedFile: (id: number | null) => void;
  inheritedNotice: string;
  newTopicNotice: boolean;
  memoryCandidate: boolean;
  clarificationRound: 1 | 2;
  clarificationOrganizations: string[];
  setClarificationOrganizations: (value: string[]) => void;
  clarificationOwner: string;
  setClarificationOwner: (value: string) => void;
  draft: string;
  setDraft: (value: string) => void;
  fileRef: RefObject<HTMLInputElement | null>;
  onOpenScope: () => void;
  onOrganizationsChange: (organizationIds: string[]) => void;
  onStop: () => void;
  onRetry: () => void;
  onConfirmClarification: () => void;
  onFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onDeleteFile: (file: DemoFile) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent) => void;
  onSuggestion: (question: string) => void;
  onNotify: (message: string) => void;
  onSaveMemory: () => void;
  onDismissMemory: () => void;
  language: UiLanguage;
}) {
  const isProcessing = ["understanding", "working", "composing"].includes(stage);
  const usableFiles = files.filter((file) => file.status === "可使用" || file.status === "部分解析");
  const copy = workbenchCopy[language];

  return (
    <div className="chat-page">
      <div className="chat-scroll-region">
        <div className="chat-scroll-inner">
          {(route === "data" || route === "failure") && (
            <button type="button" className="scope-bar" onClick={onOpenScope}>
              <span><small>当前范围</small><strong>{scope.time} · {formatOrganizationSelection(scope.organizationIds, language)}{scope.owner ? ` · ${scope.owner}` : ""}{scope.object ? ` · ${scope.object}` : ""}</strong></span>
              <span>查看或调整</span>
            </button>
          )}
          {route === "file" && (
            <div className="scope-bar static"><span><small>当前会话文件</small><strong>{files.length} 个文件，{usableFiles.length} 个可使用</strong></span><span>不会跨会话检索</span></div>
          )}
          {inheritedNotice && <p className="context-notice">{inheritedNotice}</p>}
          {newTopicNotice && <p className="context-notice">这是一个新的主题，已在当前会话中继续处理。</p>}

          <div className="conversation-column">
        {previousQuestion && (
          <details className="previous-turn"><summary>上一轮对话</summary><p>{previousQuestion}</p></details>
        )}
        {question ? (
          <article className="user-message"><span>您</span><p>{question}</p><time>刚刚</time></article>
        ) : (
          <ChatEmptyState onExample={onSuggestion} onUpload={() => fileRef.current?.click()} />
        )}

        {stage === "clarifying" && (
          <ClarificationCard
            round={clarificationRound}
            selectedOrganizations={clarificationOrganizations}
            setSelectedOrganizations={setClarificationOrganizations}
            selectedOwner={clarificationOwner}
            setSelectedOwner={setClarificationOwner}
            onConfirm={onConfirmClarification}
            language={language}
          />
        )}
        {isProcessing && <ProcessingCard stage={stage} route={route} onStop={onStop} />}
        {stage === "stopped" && <StoppedCard onRetry={onRetry} />}
        {stage === "offline" && <OfflineMessage onRetry={onRetry} />}
        {stage === "ready" && (
          <>
            {route === "data" && <StructuredAnswer answer={answer} version={answerVersion} onSuggestion={onSuggestion} onNotify={onNotify} />}
            {route === "file" && <FileAnswer files={usableFiles} deleted={files.length === 0} onSuggestion={onSuggestion} onNotify={onNotify} />}
            {route === "general" && <GeneralAnswer question={question} onSuggestion={onSuggestion} onNotify={onNotify} />}
            {route === "research" && <ResearchAnswer onSuggestion={onSuggestion} onNotify={onNotify} />}
            {route === "failure" && <FailureAnswer onRetry={onRetry} onOpenScope={onOpenScope} />}
          </>
        )}

        {memoryCandidate && stage === "ready" && (
          <section className="memory-candidate" aria-labelledby="memory-candidate-title">
            <div><p className="eyebrow">可选长期偏好</p><h3 id="memory-candidate-title">以后金额使用万元，并先给结论</h3><p>只有确认后才会保存。一次查询不会自动形成长期记忆。</p></div>
            <div><button type="button" className="primary-button compact" onClick={onSaveMemory}>保存偏好</button><button type="button" className="text-button" onClick={onDismissMemory}>仅本次使用</button></div>
          </section>
        )}

        {files.length > 0 && (
          <FileList files={files} selectedFile={selectedFile} setSelectedFile={setSelectedFile} onDelete={onDeleteFile} />
        )}
          </div>
        </div>
      </div>

      <div className="workspace-composer-dock chat-dock">
        <form className="composer workbench-composer chat-composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="chat-question">继续提问</label>
          <textarea id="chat-question" rows={2} maxLength={COMPOSER_MAX_LENGTH} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onKeyDown} placeholder={copy.continuePlaceholder} />
          <div className="composer-footer">
            <div className="composer-tools">
              <input ref={fileRef} className="sr-only" type="file" multiple accept=".pdf,.docx,.xlsx,.pptx" onChange={onFiles} />
              <button type="button" className="composer-tool-button" onClick={() => fileRef.current?.click()} aria-label="添加文件"><span aria-hidden="true">＋</span><span>{copy.file}</span></button>
              {(route === "data" || route === "failure") && <OrganizationPicker language={language} selectedIds={scope.organizationIds} onApply={onOrganizationsChange} />}
            </div>
            <div className="composer-send">
              {draft.length >= COMPOSER_HINT_THRESHOLD && <span className="composer-character-count" aria-live="polite">{copy.remainingCharacters(COMPOSER_MAX_LENGTH - draft.length)}</span>}
              <button className="composer-submit-button" type="submit" disabled={!draft.trim() || isProcessing} aria-label="发送">↑</button>
            </div>
          </div>
        </form>
        <p>{copy.disclaimer}</p>
      </div>
    </div>
  );
}

export function UiIcon({ name }: { name: UiIconName }) {
  const paths: Record<UiIconName, ReactNode> = {
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.9 1.9-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1 1.55V20h-2.7v-.09a1.7 1.7 0 0 0-1.07-1.55 1.7 1.7 0 0 0-1.88.34l-.06.06-1.9-1.9.06-.06A1.7 1.7 0 0 0 7.75 15a1.7 1.7 0 0 0-1.55-1H6v-2.7h.09a1.7 1.7 0 0 0 1.55-1.07 1.7 1.7 0 0 0-.34-1.88l-.06-.06 1.9-1.9.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 12.1 5.2V5h2.7v.09a1.7 1.7 0 0 0 1.07 1.55 1.7 1.7 0 0 0 1.88-.34l.06-.06 1.9 1.9-.06.06a1.7 1.7 0 0 0-.34 1.88A1.7 1.7 0 0 0 20.8 11v2.7h-.09A1.7 1.7 0 0 0 19.4 15Z" /></>,
    language: <><circle cx="12" cy="12" r="8.5" /><path d="M3.8 12h16.4M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5S14.3 18.1 12 20.5M12 3.5C9.7 5.9 8.6 8.7 8.6 12s1.1 6.1 3.4 8.5" /></>,
    logout: <><path d="M10 5H6.5A2.5 2.5 0 0 0 4 7.5v9A2.5 2.5 0 0 0 6.5 19H10" /><path d="m14 8 4 4-4 4M18 12H9" /></>,
    chevron: <path d="m9 6 6 6-6 6" />,
    search: <><circle cx="10.5" cy="10.5" r="6" /><path d="m15 15 4.5 4.5" /></>,
    check: <path d="m5 12 4 4 10-10" />,
    profile: <><circle cx="12" cy="8" r="3.5" /><path d="M5.5 19c.8-3.2 3-5 6.5-5s5.7 1.8 6.5 5" /></>,
    appearance: <><circle cx="12" cy="12" r="8.5" /><path d="M12 3.5v17M3.5 12h17M6 6l12 12M18 6 6 18" /></>,
    memory: <><path d="M7 5.5h8.5A2.5 2.5 0 0 1 18 8v10l-6-3-6 3V6.5A1 1 0 0 1 7 5.5Z" /><path d="M9 9h6" /></>,
    system: <><rect x="3.5" y="4.5" width="17" height="11" rx="2" /><path d="M9 19.5h6M12 15.5v4" /></>,
    light: <><circle cx="12" cy="12" r="3.5" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4" /></>,
    dark: <path d="M19.5 15.5A8 8 0 0 1 8.5 4.5a8.2 8.2 0 1 0 11 11Z" />,
    edit: <><path d="m5 16-.7 3.7L8 19l9.8-9.8-3-3L5 16Z" /><path d="m13.8 7.2 3 3" /></>,
    shield: <><path d="M12 3.5 19 6v5.4c0 4.2-2.3 7.1-7 9.1-4.7-2-7-4.9-7-9.1V6l7-2.5Z" /><path d="m9 12 2 2 4-4" /></>,
    pin: <><path d="m14 4 6 6-3 1-3.5 3.5 1 3-1.5 1.5-4-4-4.5 4.5" /><path d="m7 8 3 1L13.5 5l.5-1Z" /></>,
    archive: <><rect x="4" y="5" width="16" height="4" rx="1" /><path d="M6 9v9.5h12V9M10 13h4" /></>,
    remove: <><path d="M5 5l14 14M19 5 5 19" /></>,
    folder: <><path d="M3.5 7.5h6l2-2h8a1.5 1.5 0 0 1 1.5 1.5v10.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a1.5 1.5 0 0 1 .5-1.5Z" /><path d="M3.5 9h17.5" /></>,
  };
  return <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

export function PersonalCenterWindow({
  view,
  setView,
  onClose,
  themePreference,
  onThemePreferenceChange,
  language,
  profile,
  onProfileChange,
  scope,
  memoryEnabled,
  setMemoryEnabled,
  memories,
  onSaveMemory,
  onDeleteMemory,
  onClearMemories,
  onOpenMemorySource,
  onNotify,
}: {
  view: PersonalCenterView;
  setView: (view: PersonalCenterView) => void;
  onClose: () => void;
  themePreference: ThemePreference;
  onThemePreferenceChange: (theme: ThemePreference) => void;
  language: UiLanguage;
  profile: ExecutiveProfile;
  onProfileChange: (profile: ExecutiveProfile) => void;
  scope: ScopeState;
  memoryEnabled: boolean;
  setMemoryEnabled: (value: boolean) => void;
  memories: MemoryItem[];
  onSaveMemory: (memory: MemoryItem) => void;
  onDeleteMemory: (memory: MemoryItem) => void;
  onClearMemories: () => void;
  onOpenMemorySource: () => void;
  onNotify: (message: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftProfile, setDraftProfile] = useState(profile);
  const dialogRef = useRef<HTMLDivElement>(null);
  const organizationSummary = formatOrganizationSelection(scope.organizationIds, language, true);
  const labels = language === "en"
    ? { title: "Personal settings", back: "Back to workspace", profile: "Profile", appearance: "Appearance", memory: "Long-term memory", close: "Close", edit: "Edit profile" }
    : language === "zh-TW"
      ? { title: "個人設定", back: "返回工作台", profile: "個人資料", appearance: "外觀", memory: "長期記憶", close: "關閉", edit: "編輯資料" }
      : { title: "个人设置", back: "返回工作台", profile: "个人资料", appearance: "外观", memory: "长期记忆", close: "关闭", edit: "编辑资料" };

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLElement>("button, input, select")?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  function saveProfile(event: FormEvent) {
    event.preventDefault();
    const nextProfile = { ...draftProfile, displayName: draftProfile.displayName.trim() || profile.displayName, salutation: draftProfile.salutation.trim() || profile.salutation };
    onProfileChange(nextProfile);
    setDraftProfile(nextProfile);
    setEditing(false);
    onNotify("个人资料已更新，问候语将使用新的称呼");
  }

  return (
    <div className="preferences-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} className="preferences-window" role="dialog" aria-modal="true" aria-labelledby="preferences-title">
        <aside className="preferences-sidebar">
          <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
          <button type="button" className="preferences-back" onClick={onClose}><span aria-hidden="true">←</span>{labels.back}</button>
          <div className="preferences-heading"><small>{labels.title}</small><strong id="preferences-title">Ryan.Zhang</strong></div>
          <nav aria-label={labels.title}>
            <button type="button" className={view === "profile" ? "active" : ""} onClick={() => setView("profile")}><UiIcon name="profile" /><span>{labels.profile}</span></button>
            <button type="button" className={view === "appearance" ? "active" : ""} onClick={() => setView("appearance")}><UiIcon name="appearance" /><span>{labels.appearance}</span></button>
            <button type="button" className={view === "memory" ? "active" : ""} onClick={() => setView("memory")}><UiIcon name="memory" /><span>{labels.memory}</span></button>
          </nav>
          <div className="preferences-privacy"><UiIcon name="shield" /><span><strong>仅您可见</strong><small>偏好与记忆不会向企业管理员展示</small></span></div>
        </aside>

        <main className="preferences-main">
          <header className="preferences-main-header"><div><small>{labels.title}</small><strong>{view === "profile" ? labels.profile : view === "appearance" ? labels.appearance : labels.memory}</strong></div><button type="button" onClick={onClose} aria-label={labels.close}>×</button></header>

          {view === "profile" && (
            <div className="profile-settings-pane">
              <section className="profile-hero">
                <span className="profile-hero-avatar" aria-hidden="true">RZ</span>
                <div><h1>{profile.displayName}</h1><p>{profile.salutation} · {organizationSummary}</p><small>{profile.emailMasked}</small></div>
                {!editing && <button type="button" className="profile-edit-button" onClick={() => { setDraftProfile(profile); setEditing(true); }}><UiIcon name="edit" />{labels.edit}</button>}
              </section>

              <section className="profile-summary-rail" aria-label="个性化摘要">
                <div><small>专属称呼</small><strong>{profile.salutation}</strong><span>用于首页问候与服务语气</span></div>
                <div><small>默认数据范围</small><strong>{organizationSummary}</strong><span>由当前可用数据权限决定</span></div>
                <div><small>金额单位</small><strong>{profile.amountUnit}</strong><span>用于经营数字的默认表达</span></div>
              </section>

              {editing ? (
                <form className="profile-edit-form" onSubmit={saveProfile}>
                  <div className="profile-section-title"><span>编辑个性化资料</span><small>保存后立即用于新的会话</small></div>
                  <div className="profile-form-grid">
                    <label><span>显示名称</span><input value={draftProfile.displayName} onChange={(event) => setDraftProfile({ ...draftProfile, displayName: event.target.value })} maxLength={32} autoFocus /></label>
                    <label><span>专属称呼</span><input value={draftProfile.salutation} onChange={(event) => setDraftProfile({ ...draftProfile, salutation: event.target.value })} maxLength={16} placeholder="例如：张总、Ryan" /></label>
                    <label><span>默认金额单位</span><select value={draftProfile.amountUnit} onChange={(event) => setDraftProfile({ ...draftProfile, amountUnit: event.target.value })}><option>万元</option><option>亿元</option><option>元</option></select></label>
                  </div>
                  <div className="profile-form-actions"><button type="button" onClick={() => { setEditing(false); setDraftProfile(profile); }}>取消</button><button type="submit">保存资料</button></div>
                </form>
              ) : (
                <div className="profile-detail-grid">
                  <section><div className="profile-section-title"><span>服务偏好</span><small>影响表达，不改变数据权限</small></div><dl><div><dt>问候预览</dt><dd>早上好，{profile.salutation}</dd></div><div><dt>回答风格</dt><dd>先给结论，再展开依据</dd></div><div><dt>关键数字</dt><dd>默认使用{profile.amountUnit}</dd></div></dl></section>
                  <section><div className="profile-section-title"><span>账号与安全</span><small>只展示必要信息</small></div><dl><div><dt>登录邮箱</dt><dd>{profile.emailMasked}</dd></div><div><dt>最近登录</dt><dd>{profile.lastLoginAt}</dd></div><div><dt>账号状态</dt><dd><span className="profile-status-dot" />正常</dd></div></dl></section>
                </div>
              )}
            </div>
          )}

          {view === "appearance" && (
            <div className="appearance-settings-pane">
              <header><p className="eyebrow">界面显示</p><h1>选择适合您的外观</h1><p>只改变界面明暗，不影响会话、数据或长期记忆。</p></header>
              <div className="appearance-options" role="radiogroup" aria-label="外观模式">
                {([
                  ["system", "跟随系统", "随电脑的深浅色自动切换", "system"],
                  ["light", "白天", "温和暖白，适合明亮环境", "light"],
                  ["dark", "夜间", "低眩光深灰，适合夜间使用", "dark"],
                ] as Array<[ThemePreference, string, string, UiIconName]>).map(([id, title, description, icon]) => (
                  <button type="button" key={id} role="radio" aria-checked={themePreference === id} className={themePreference === id ? "selected" : ""} onClick={() => onThemePreferenceChange(id)}>
                    <span className={`appearance-preview ${id}`}><span /><span /><span /></span>
                    <span className="appearance-option-copy"><i><UiIcon name={icon} /></i><span><strong>{title}</strong><small>{description}</small></span></span>
                    <span className="appearance-radio" aria-hidden="true" />
                  </button>
                ))}
              </div>
              <section className="appearance-composer-preview" aria-label="聊天框预览"><small>预览</small><div><span>向 AI 秘书提问经营数据</span><i>↑</i></div><p>聊天框保留若隐若现的立体阴影，长时间使用也不过度抢眼。</p></section>
            </div>
          )}

          {view === "memory" && (
            <div className="preferences-memory-pane">
              <MemoryView enabled={memoryEnabled} setEnabled={setMemoryEnabled} memories={memories} onSave={onSaveMemory} onDelete={onDeleteMemory} onClear={onClearMemories} onOpenSource={onOpenMemorySource} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export function OrganizationPicker({ language, selectedIds, onApply }: { language: UiLanguage; selectedIds: string[]; onApply: (organizationIds: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const [draftIds, setDraftIds] = useState(selectedIds);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const copy = workbenchCopy[language];
  const normalizedQuery = query.trim().toLocaleLowerCase(language);
  const filteredOrganizations = availableOrganizations.filter((organization) =>
    organization.labels[language].toLocaleLowerCase(language).includes(normalizedQuery),
  );

  useEffect(() => {
    if (!open) return;
    window.requestAnimationFrame(() => searchRef.current?.focus());
    const closeOnOutside = (event: PointerEvent) => {
      if (rootRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    window.addEventListener("pointerdown", closeOnOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("pointerdown", closeOnOutside);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  function togglePicker() {
    if (!open) {
      setDraftIds(selectedIds.length ? selectedIds : [ALL_ORGANIZATIONS_ID]);
      setQuery("");
    }
    setOpen((current) => !current);
  }

  function applySelection() {
    onApply(draftIds.length ? draftIds : [ALL_ORGANIZATIONS_ID]);
    setOpen(false);
    triggerRef.current?.focus();
  }

  return (
    <div ref={rootRef} className="organization-picker">
      <button
        ref={triggerRef}
        type="button"
        className="composer-tool-button scope"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={togglePicker}
      >
        <span className="scope-building-mark" aria-hidden="true" />
        <span>{formatOrganizationSelection(selectedIds, language, true)}</span>
        <span className="organization-picker-chevron" aria-hidden="true">{open ? "⌃" : "⌄"}</span>
      </button>
      {open && (
        <section className="organization-popover" role="dialog" aria-modal="false" aria-labelledby="organization-picker-title">
          <header><strong id="organization-picker-title">{copy.chooseOrganization}</strong></header>
          <label className="organization-search">
            <UiIcon name="search" />
            <span className="sr-only">{copy.searchOrganization}</span>
            <input ref={searchRef} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={copy.searchOrganization} />
          </label>
          <div className="organization-options" role="listbox" aria-multiselectable="true">
            {filteredOrganizations.length ? filteredOrganizations.map((organization) => {
              const selected = draftIds.includes(organization.id);
              return (
                <button
                  type="button"
                  key={organization.id}
                  className={selected ? "selected" : ""}
                  role="option"
                  aria-selected={selected}
                  onClick={() => setDraftIds((current) => toggleOrganizationSelection(current, organization.id))}
                >
                  <span className="organization-check" aria-hidden="true">{selected ? "✓" : ""}</span>
                  <span>{organization.labels[language]}</span>
                  {selected && <UiIcon name="check" />}
                </button>
              );
            }) : <p className="organization-empty">{copy.noOrganizations}</p>}
          </div>
          <footer><small>{copy.configuredByAdmin}</small><button type="button" onClick={applySelection}>{copy.apply}</button></footer>
        </section>
      )}
    </div>
  );
}

export function ChatEmptyState({ onExample, onUpload }: { onExample: (question: string) => void; onUpload: () => void }) {
  return (
    <section className="chat-empty-state">
      <p className="eyebrow">新会话</p><h2>直接说您想完成的事</h2><p>无需选择数据、文件或写作模式，系统会先判断范围。</p>
      <div><button type="button" onClick={() => onExample("这个月整体经营怎么样？")}>这个月整体经营怎么样？</button><button type="button" onClick={() => onExample("哪些项目可能延期？")}>哪些项目可能延期？</button><button type="button" onClick={onUpload}>上传当前会话文件</button></div>
    </section>
  );
}

export function ClarificationCard({
  round,
  selectedOrganizations,
  setSelectedOrganizations,
  selectedOwner,
  setSelectedOwner,
  onConfirm,
  language,
}: {
  round: 1 | 2;
  selectedOrganizations: string[];
  setSelectedOrganizations: (value: string[]) => void;
  selectedOwner: string;
  setSelectedOwner: (value: string) => void;
  onConfirm: () => void;
  language: UiLanguage;
}) {
  return (
    <article className="clarification-card">
      <header><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>{round === 1 ? "您希望查看哪个范围？" : "需要比较哪些负责人？"}</strong><span>范围确认 {round}/2，确认后将自动继续原问题</span></div></header>
      {round === 1 ? (
        <div className="choice-grid">
          {availableOrganizations.map((organization) => {
            const checked = selectedOrganizations.includes(organization.id);
            return <label key={organization.id} className={checked ? "selected" : ""}><input type="checkbox" checked={checked} onChange={() => setSelectedOrganizations(toggleOrganizationSelection(selectedOrganizations, organization.id))} /><span>{organization.labels[language]}</span></label>;
          })}
        </div>
      ) : (
        <div className="choice-grid">
          {["全部负责人", ...owners].map((owner) => <label key={owner} className={selectedOwner === owner ? "selected" : ""}><input type="radio" name="owner" checked={selectedOwner === owner} onChange={() => setSelectedOwner(owner)} /><span>{owner}</span></label>)}
        </div>
      )}
      <footer><p>{round === 1 ? "支持单选、多选或全部。" : "这是最后一轮范围确认。"}</p><button type="button" className="primary-button" onClick={onConfirm}>{round === 1 ? "继续" : "确认并查询"}</button></footer>
    </article>
  );
}

export function ProcessingCard({ stage, route, onStop }: { stage: ChatStage; route: RouteKind; onStop: () => void }) {
  const routeCopy = route === "file" ? "正在读取当前会话文件" : route === "research" ? "正在检索公开信息" : route === "general" ? "正在整理材料" : "正在核对经营数据";
  const title = stage === "understanding" ? "正在理解您的问题" : stage === "working" ? routeCopy : "正在整理结论";
  return (
    <article className="processing-card" role="status" aria-live="polite">
      <header><span className="assistant-monogram pulse" aria-hidden="true">秘</span><div><strong>{title}</strong><span>不会展示内部推理，也不会猜测企业数字</span></div><button type="button" onClick={onStop}>停止</button></header>
      <div className="processing-progress"><span className={stage !== "understanding" ? "complete" : "active"}>理解问题</span><span className={stage === "working" ? "active" : stage === "composing" ? "complete" : ""}>核对内容</span><span className={stage === "composing" ? "active" : ""}>整理结论</span></div>
      <div className="answer-skeleton" aria-hidden="true"><span /><span /><span /></div>
    </article>
  );
}

export function StoppedCard({ onRetry }: { onRetry: () => void }) {
  return <article className="state-card attention"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>回答已停止</strong><p>已生成的内容会保留。您可以使用相同问题和范围重新生成。</p></div><button type="button" className="secondary-button" onClick={onRetry}>重新生成</button></article>;
}

export function OfflineMessage({ onRetry }: { onRetry: () => void }) {
  return <article className="state-card risk"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>消息已保留，尚未确认送达</strong><p>网络恢复后会先查询任务状态。后端未收到请求时才允许重新发送。</p></div><button type="button" className="secondary-button" onClick={onRetry}>查询状态并重试</button></article>;
}

export function StructuredAnswer({ answer, version, onSuggestion, onNotify }: { answer: AnswerConfig; version: number; onSuggestion: (question: string) => void; onNotify: (message: string) => void }) {
  const [chartMode, setChartMode] = useState<"chart" | "table">("chart");
  const [selectedPoint, setSelectedPoint] = useState(0);
  const copyText = `${answer.title}\n\n${answer.summary}\n\n数据截至：${answer.asOf}`;

  return (
    <article className={`structured-answer layout-${answer.layout}`} aria-live="polite">
      <header className="answer-meta"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>已完成核对</strong><span>{version > 1 ? `重试版本 ${version}` : "首次回答"}</span></div><time>数据截至 {answer.asOf}</time></header>
      <section className="answer-conclusion">
        <span className="answer-label">{answer.label}</span><h2>{answer.title}</h2><p>{answer.summary}</p>
        <div className="answer-actions"><button type="button" onClick={() => copyToClipboard(copyText, onNotify, "结论已复制")}>复制结论</button><button type="button" onClick={() => copyToClipboard(fullAnswerText(answer), onNotify, "完整回答已复制")}>复制完整回答</button>{answer.chart && <button type="button" onClick={() => saveChartImage(answer, onNotify)}>保存图表</button>}</div>
      </section>
      <section className="metric-grid" aria-label="关键指标">
        {answer.metrics.map((metric) => <Metric key={metric.label} {...metric} />)}
      </section>
      <section className="answer-sections" aria-label="经营板块摘要">
        {answer.sections.map((section, index) => <article key={section.title}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{section.title}</h3><p>{section.body}</p></div>{section.tone && <StatusBadge tone={section.tone} label={toneLabel(section.tone)} />}</article>)}
      </section>
      {answer.chart && (
        <section className="chart-card" aria-labelledby={`chart-${answer.id}`}>
          <header><div><h3 id={`chart-${answer.id}`}>{answer.chart.title}</h3><p>单位：{answer.chart.unit} · {answer.scope}</p></div><div className="segmented-control"><button type="button" className={chartMode === "chart" ? "active" : ""} onClick={() => setChartMode("chart")}>图表</button><button type="button" className={chartMode === "table" ? "active" : ""} onClick={() => setChartMode("table")}>数据表</button></div></header>
          {chartMode === "chart" ? <DataChart chart={answer.chart} selected={selectedPoint} onSelect={setSelectedPoint} /> : <ChartTable chart={answer.chart} />}
        </section>
      )}
      {answer.rows && answer.columns && <AnswerTable columns={answer.columns} rows={answer.rows} />}
      <div className="evidence-action-grid">
        <section><p className="eyebrow">可核对证据</p><h3>结论依据</h3><ol>{answer.evidence.map((item, index) => <li key={item}><span>{index + 1}</span>{item}</li>)}</ol></section>
        <section><p className="eyebrow">建议动作</p><h3>优先处理</h3><ol>{answer.actions.map((item, index) => <li key={item}><span>{index + 1}</span>{item}</li>)}</ol></section>
      </div>
      <details className="source-details"><summary>查看数据范围、来源与口径</summary><div><dl><div><dt>时间与组织范围</dt><dd>{answer.scope}</dd></div><div><dt>数据截止时间</dt><dd>{answer.asOf}</dd></div><div><dt>指标口径</dt><dd>{answer.definition}</dd></div><div><dt>数据来源</dt><dd>{answer.sources.join("；")}</dd></div></dl><p>本页使用演示样本展示原型能力，不代表任何真实企业经营情况。</p></div></details>
      <FollowUps questions={answer.followups} onSelect={onSuggestion} />
    </article>
  );
}

export function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone: Tone }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong><small className={tone}>{note}</small></div>;
}

export function DataChart({ chart, selected, onSelect }: { chart: NonNullable<AnswerConfig["chart"]>; selected: number; onSelect: (index: number) => void }) {
  const max = Math.max(...chart.data.map((item) => item.value));
  if (chart.kind === "line") {
    const points = chart.data.map((item, index) => `${(index / Math.max(chart.data.length - 1, 1)) * 92 + 4},${92 - (item.value / max) * 72}`).join(" ");
    return (
      <div className="line-chart" role="img" aria-label={`${chart.title}，${chart.data.map((item) => `${item.label} ${item.display}`).join("，")}`}>
        <div className="selected-chart-value"><span>{chart.data[selected].label}</span><strong>{chart.data[selected].display}</strong></div>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><line x1="4" y1="92" x2="96" y2="92" /><line x1="4" y1="56" x2="96" y2="56" /><line x1="4" y1="20" x2="96" y2="20" /><polyline points={points} /></svg>
        <div className="chart-points">{chart.data.map((item, index) => <button key={item.label} type="button" className={selected === index ? "active" : ""} onClick={() => onSelect(index)}><span>{item.display}</span><small>{item.label}</small></button>)}</div>
      </div>
    );
  }
  if (chart.kind === "progress") {
    const actual = chart.data[0]; const target = chart.data[1]; const percentage = Math.min((actual.value / target.value) * 100, 100);
    return <div className="progress-chart"><div className="progress-numbers"><span><small>{actual.label}</small><strong>{actual.display}</strong></span><span><small>{target.label}</small><strong>{target.display}</strong></span></div><div className="progress-track"><span style={{ width: `${percentage}%` }} /></div><p>当前完成 {percentage.toFixed(1)}%，剩余 {(target.value - actual.value).toLocaleString("zh-CN")} {chart.unit}</p></div>;
  }
  if (chart.kind === "stacked") {
    const total = chart.data.reduce((sum, item) => sum + item.value, 0);
    return <div className="stacked-chart"><div className="stacked-track">{chart.data.map((item, index) => <button type="button" key={item.label} className={`segment segment-${index + 1}`} style={{ width: `${(item.value / total) * 100}%` }} onClick={() => onSelect(index)} aria-label={`${item.label} ${item.display}`} />)}</div><div className="stacked-legend">{chart.data.map((item, index) => <button type="button" key={item.label} className={selected === index ? "active" : ""} onClick={() => onSelect(index)}><span className={`legend-dot segment-${index + 1}`} /><small>{item.label}</small><strong>{item.display}</strong></button>)}</div></div>;
  }
  return <div className="bar-comparison" role="img" aria-label={`${chart.title}，${chart.data.map((item) => `${item.label} ${item.display}`).join("，")}`}>{chart.data.map((item, index) => <button type="button" key={item.label} className={selected === index ? "active" : ""} onClick={() => onSelect(index)}><span className="bar-label">{item.label}</span><span className="horizontal-track"><span style={{ width: `${(item.value / max) * 100}%` }} /></span><strong>{item.display}</strong></button>)}</div>;
}

export function ChartTable({ chart }: { chart: NonNullable<AnswerConfig["chart"]> }) {
  return <div className="table-wrap"><table><thead><tr><th>对象 / 时间</th><th>数值</th><th>单位</th></tr></thead><tbody>{chart.data.map((item) => <tr key={item.label}><td>{item.label}</td><td>{item.display}</td><td>{chart.unit}</td></tr>)}</tbody></table></div>;
}

export function AnswerTable({ columns, rows }: { columns: NonNullable<AnswerConfig["columns"]>; rows: NonNullable<AnswerConfig["rows"]> }) {
  const [expanded, setExpanded] = useState(false);
  return <section className="answer-table-section"><header><div><p className="eyebrow">相关明细</p><h3>当前回答的重点记录</h3></div><button type="button" className="text-button" onClick={() => setExpanded((current) => !current)}>{expanded ? "收起明细" : "查看全部"}</button></header><div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.slice(0, expanded ? 10 : 4).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column.key}>{row[column.key]}</td>)}</tr>)}</tbody></table></div></section>;
}

export function FileAnswer({ files, deleted, onSuggestion, onNotify }: { files: DemoFile[]; deleted: boolean; onSuggestion: (question: string) => void; onNotify: (message: string) => void }) {
  if (!files.length) {
    return <article className="structured-answer"><header className="answer-meta"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>当前会话没有可用文件</strong><span>不会检索其他会话文件</span></div></header><section className="answer-conclusion"><span className="answer-label">文件范围</span><h2>{deleted ? "来源文件已删除，历史回答文字仍保留" : "请先上传并等待文件完成解析"}</h2><p>只有状态为“可使用”或“部分解析”的文件会进入本轮问答。</p></section></article>;
  }
  const source = files[0];
  return <article className="structured-answer layout-diagnosis"><header className="answer-meta"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>已读取当前会话文件</strong><span>{files.length} 个文件可使用</span></div><time>解析完成 刚刚</time></header><section className="answer-conclusion"><span className="answer-label">文件问答</span><h2>报告提到的三个主要问题集中在验收、资源排期和责任闭环</h2><p>结论只来自当前会话的《{source.name}》，未检索其他会话或企业数据库。</p><div className="answer-actions"><button type="button" onClick={() => copyToClipboard("三个主要问题：验收确认、资源排期、责任闭环。", onNotify, "结论已复制")}>复制结论</button></div></section><section className="document-findings"><article><span>01</span><div><h3>验收窗口未形成共同确认</h3><p>报告记录客户与项目组对验收日期仍有差异。</p><small>来源：《{source.name}》第 4 页</small></div></article><article><span>02</span><div><h3>交付资源排期晚于里程碑要求</h3><p>关键测试资源与原计划相比晚一周到位。</p><small>来源：《{source.name}》第 7 页</small></div></article><article><span>03</span><div><h3>问题责任人和完成日期不完整</h3><p>复盘清单有两项行动未填写明确负责人。</p><small>来源：《{source.name}》第 11 页</small></div></article></section><details className="source-details"><summary>查看文件范围与解析说明</summary><div><dl><div><dt>当前文件</dt><dd>{files.map((file) => file.name).join("；")}</dd></div><div><dt>解析范围</dt><dd>{files.map((file) => file.range).join("；")}</dd></div><div><dt>检索范围</dt><dd>仅当前会话</dd></div></dl><p>原型只模拟解析结果，不读取或上传文件正文到外部服务。</p></div></details><FollowUps questions={["把三个问题按影响排序。", "报告中每个问题的负责人是谁？", "整理成一页项目复盘备忘录。"]} onSelect={onSuggestion} /></article>;
}

export function GeneralAnswer({ question, onSuggestion, onNotify }: { question: string; onSuggestion: (question: string) => void; onNotify: (message: string) => void }) {
  return <article className="structured-answer"><header className="answer-meta"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>已整理材料</strong><span>未调用企业数据</span></div><time>刚刚</time></header><section className="answer-conclusion"><span className="answer-label">决策与写作</span><h2>{question.includes("万元") ? "已按本轮要求使用万元，并将结论放在最前" : "经营会汇报应先讲清差距，再明确三项当周动作"}</h2><p>下面内容是可继续修改的草稿，不包含未经提供的负责人和日期。</p><div className="answer-actions"><button type="button" onClick={() => copyToClipboard("结论：回款和交付偏差需要优先处理。行动：确认回款节点、锁定验收窗口、保持高概率商机推进。", onNotify, "草稿已复制")}>复制草稿</button></div></section><section className="memo-block"><p className="eyebrow">三分钟汇报提纲</p><h3>本周经营会</h3><dl><div><dt>结论</dt><dd>整体接近计划，回款和两个项目的里程碑偏差需要优先处理。</dd></div><div><dt>依据</dt><dd>收入完成 82.4%，回款低于计划 8.6 个百分点，两个项目进入延期关注。</dd></div><div><dt>影响</dt><dd>若验收未按本月完成，收入确认节奏会受到影响。</dd></div><div><dt>行动</dt><dd>确认逾期回款节点、锁定项目验收窗口、保持华东高概率商机推进。</dd></div></dl></section><FollowUps questions={["改成董事会书面备忘录。", "把行动项整理成表格。", "压缩成一封内部邮件。"]} onSelect={onSuggestion} /></article>;
}

export function ResearchAnswer({ onSuggestion, onNotify }: { onSuggestion: (question: string) => void; onNotify: (message: string) => void }) {
  return <article className="structured-answer"><header className="answer-meta"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>已完成公开信息检索</strong><span>检索日期 2026-07-26</span></div><time>演示来源</time></header><section className="answer-conclusion"><span className="answer-label">公开研究</span><h2>近期变化集中在行业数字化投入结构、数据合规要求与客户采购节奏</h2><p>以下为原型中的演示研究结构。公开事实与对企业的分析判断已经分开，未向外部搜索发送内部金额、客户名或文件内容。</p><div className="answer-actions"><button type="button" onClick={() => copyToClipboard("公开研究结论：数字化投入结构、数据合规要求与客户采购节奏值得关注。", onNotify, "研究结论已复制")}>复制结论</button></div></section><div className="research-grid"><section><p className="eyebrow">公开事实</p><h3>可核对信息</h3><ol><li><strong>政策与合规</strong><span>企业数据处理和跨系统连接仍需遵循最小必要原则。</span></li><li><strong>采购节奏</strong><span>公开采购信息显示，部分大型项目的决策周期趋于延长。</span></li><li><strong>投入结构</strong><span>企业更关注可验证的业务结果，而非单纯增加工具数量。</span></li></ol></section><section><p className="eyebrow">分析判断</p><h3>对企业可能的影响</h3><ol><li><span>项目方案应提前说明数据边界、部署方式和可审计记录。</span></li><li><span>预测签约时需要为采购与合规确认预留更充分时间。</span></li><li><span>管理层材料应优先呈现可核对结果和落地责任。</span></li></ol></section></div><section className="public-sources"><p className="eyebrow">演示来源链接</p><h3>公开来源</h3><a href="https://www.miit.gov.cn/" target="_blank" rel="noreferrer">工业和信息化部 · 公开信息入口</a><a href="https://www.stats.gov.cn/" target="_blank" rel="noreferrer">国家统计局 · 公开数据入口</a><p>本原型不执行实时 Anspire 搜索，来源与结论仅用于展示交互和信息结构。</p></section><FollowUps questions={["把公开事实按时间排序。", "哪些判断需要进一步验证？", "整理成一页行业变化备忘录。"]} onSelect={onSuggestion} /></article>;
}

export function FailureAnswer({ onRetry, onOpenScope }: { onRetry: () => void; onOpenScope: () => void }) {
  return <article className="structured-answer failure-answer"><header className="answer-meta"><span className="assistant-monogram" aria-hidden="true">秘</span><div><strong>本次未取得回款数据</strong><span>没有生成近似金额</span></div><time>最近成功数据 7月24日 02:04</time></header><section className="answer-conclusion"><span className="answer-label risk">数据同步失败</span><h2>暂时无法确认本月回款金额</h2><p>回款数据同步任务在读取计划回款日字段时失败。商机与项目数据不受影响，但不能用它们推测回款数字。</p></section><dl className="failure-facts"><div><dt>发生了什么</dt><dd>经营财务与回款数据本次同步失败。</dd></div><div><dt>无法完成的原因</dt><dd>计划回款日字段未通过同步校验。</dd></div><div><dt>可确认的最新时间</dt><dd>2026-07-24 02:04</dd></div><div><dt>下一步</dt><dd>可重试本次查询、调整范围，或联系数据负责人修复字段。</dd></div></dl><div className="failure-actions"><button type="button" className="primary-button" onClick={onRetry}>重试查询</button><button type="button" className="secondary-button" onClick={onOpenScope}>调整条件</button><a href="mailto:data-owner@example.invalid">联系数据负责人</a></div></article>;
}

export function FollowUps({ questions, onSelect }: { questions: string[]; onSelect: (question: string) => void }) {
  return <section className="followups"><p className="eyebrow">继续追问</p><h3>下一步可以问</h3><div>{questions.slice(0, 3).map((question, index) => <button type="button" key={question} onClick={() => onSelect(question)}><span>{index + 1}</span>{question}<small>放入输入框</small></button>)}</div></section>;
}

export function FileList({ files, selectedFile, setSelectedFile, onDelete }: { files: DemoFile[]; selectedFile: number | null; setSelectedFile: (id: number | null) => void; onDelete: (file: DemoFile) => void }) {
  return <section className="file-list-section"><header><div><p className="eyebrow">当前会话附件</p><h3>{files.length} 个文件</h3></div><span>文件不会自动跨会话使用</span></header><div className="file-list">{files.map((file) => <article key={file.id}><button type="button" className="file-main" onClick={() => setSelectedFile(selectedFile === file.id ? null : file.id)}><span className="file-kind">{file.kind}</span><span><strong>{file.name}</strong><small>{file.size} · {file.uploadedAt}</small></span><StatusBadge tone={file.status === "可使用" ? "positive" : file.status === "解析失败" ? "risk" : "attention"} label={file.status} /></button><button type="button" className="danger-text-button" onClick={() => onDelete(file)}>删除</button>{selectedFile === file.id && <div className="file-detail"><dl><div><dt>解析范围</dt><dd>{file.range}</dd></div><div><dt>当前状态</dt><dd>{file.status}</dd></div>{file.error && <div><dt>失败原因</dt><dd>{file.error}</dd></div>}</dl>{file.error && <p>下一步：上传可复制文字的 PDF，或联系管理员确认扩展解析能力。</p>}</div>}</article>)}</div></section>;
}

export function HistoryView({ conversations, onOpen, onNew, onRename, onDelete }: { conversations: ConversationItem[]; onOpen: (item: ConversationItem) => void; onNew: () => void; onRename: (id: number, title: string) => void; onDelete: (item: ConversationItem) => void }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"全部" | ConversationItem["type"]>("全部");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return conversations.filter((item) => (filter === "全部" || item.type === filter) && (!normalized || `${item.title}${item.preview}${item.searchable}`.toLowerCase().includes(normalized)));
  }, [conversations, filter, query]);
  const groups = ["今天", "昨天", "更早"] as const;

  return <div className="page subpage"><section className="page-heading split"><div><p className="eyebrow">长期保留</p><h1>历史会话</h1><p>恢复当时的范围与文件关系，数据问题会按最新时间重新查询。</p></div><button type="button" className="primary-button" onClick={onNew}>新建会话</button></section><section className="history-controls"><label><span className="sr-only">搜索历史会话</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索标题、问题、摘要、客户或项目" /></label><div className="filter-tabs">{(["全部", "数据", "文件", "泛化", "每日摘要", "每周简报"] as const).map((item) => <button type="button" key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item}</button>)}</div><span>共 {filtered.length} 条</span></section>{filtered.length ? <div className="history-groups">{groups.map((group) => { const items = filtered.filter((item) => item.group === group); if (!items.length) return null; return <section key={group}><h2>{group}</h2><div className="history-list">{items.map((item) => <article key={item.id}>{editingId === item.id ? <form onSubmit={(event) => { event.preventDefault(); onRename(item.id, draft); setEditingId(null); }}><input value={draft} maxLength={20} onChange={(event) => setDraft(event.target.value)} autoFocus /><button type="submit">保存</button><button type="button" onClick={() => setEditingId(null)}>取消</button></form> : <button type="button" className="history-main" onClick={() => onOpen(item)}><span className="type-badge">{item.type}</span><span><strong>{item.title}</strong><small>{item.preview}</small></span><time>{item.time}</time></button>}<div className="history-actions"><button type="button" onClick={() => { setEditingId(item.id); setDraft(item.title); }}>改名</button><button type="button" className="danger" onClick={() => onDelete(item)}>删除</button></div></article>)}</div></section>; })}</div> : <EmptyState title="没有找到相关会话" description="换一个关键词或清除筛选条件。" action="清除筛选" onAction={() => { setQuery(""); setFilter("全部"); }} />}</div>;
}

export function MemoryView({ enabled, setEnabled, memories, onSave, onDelete, onClear, onOpenSource }: { enabled: boolean; setEnabled: (value: boolean) => void; memories: MemoryItem[]; onSave: (memory: MemoryItem) => void; onDelete: (memory: MemoryItem) => void; onClear: () => void; onOpenSource: () => void }) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const [category, setCategory] = useState("表达偏好");
  return <div className="page subpage"><section className="page-heading split"><div><p className="eyebrow">由您控制</p><h1>个人长期记忆</h1><p>只保存经确认的稳定偏好。关闭后停止读取和新增，现有内容仍可查看与删除。</p></div><button type="button" className="secondary-button" onClick={() => setAdding(true)} disabled={!enabled}>手动新增</button></section><section className="memory-master-setting"><div><strong>长期记忆</strong><p>{enabled ? "后续新消息会使用已确认的偏好。" : "已停止读取和新增，现有记忆仍保留。"}</p></div><label className="switch"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span aria-hidden="true" /><small>{enabled ? "已开启" : "已关闭"}</small></label></section>{adding && <form className="inline-form memory-add-form" onSubmit={(event) => { event.preventDefault(); if (!draft.trim()) return; onSave({ id: Date.now(), content: draft.trim(), category, createdAt: "刚刚", usedAt: "尚未使用", source: "记忆页手动新增" }); setDraft(""); setAdding(false); }}><label className="field"><span>分类</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option>表达偏好</option><option>数字偏好</option><option>默认范围</option><option>长期关注</option><option>比较口径</option></select></label><label className="field grow"><span>记忆内容</span><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="例如：对比默认使用上月同期" autoFocus /></label><button type="submit" className="primary-button compact" disabled={!draft.trim()}>保存</button><button type="button" className="text-button" onClick={() => { setAdding(false); setDraft(""); }}>取消</button></form>}<section className="memory-list-section"><header className="section-header"><div><p className="eyebrow">{memories.length} 条</p><h2>已保存记忆</h2></div>{memories.length > 0 && <button type="button" className="danger-text-button" onClick={onClear}>清空全部</button>}</header>{memories.length ? <div className="memory-list">{memories.map((memory) => <article key={memory.id}><span className="type-badge">{memory.category}</span>{editingId === memory.id ? <form onSubmit={(event) => { event.preventDefault(); onSave({ ...memory, content: draft.trim() }); setEditingId(null); }}><textarea rows={2} value={draft} onChange={(event) => setDraft(event.target.value)} autoFocus /><div><button type="submit" className="primary-button compact" disabled={!draft.trim()}>保存</button><button type="button" className="text-button" onClick={() => setEditingId(null)}>取消</button></div></form> : <div className="memory-copy"><strong>{memory.content}</strong><dl><div><dt>创建</dt><dd>{memory.createdAt}</dd></div><div><dt>最近使用</dt><dd>{memory.usedAt}</dd></div><div><dt>来源</dt><dd><button type="button" onClick={onOpenSource}>{memory.source}</button></dd></div></dl></div>}<div className="memory-actions"><button type="button" onClick={() => { setEditingId(memory.id); setDraft(memory.content); }}>修改</button><button type="button" className="danger" onClick={() => onDelete(memory)}>删除</button></div></article>)}</div> : <EmptyState title="暂无长期记忆" description="明确表达并确认的稳定偏好会显示在这里。" />}</section></div>;
}

export function DailySummaryView({ feishuPreview, onQuestion }: { feishuPreview: boolean; onQuestion: (question: string) => void }) {
  const metrics: Array<{ label: string; value: string; note: string; tone: Tone }> = [
    { label: "回款进度", value: "落后 8.6 个百分点", note: "需关注", tone: "risk" },
    { label: "交付关注", value: "2 个项目", note: "里程碑偏差", tone: "attention" },
    { label: "加权商机", value: "+5.1%", note: "较上月同期改善", tone: "positive" },
  ];
  const questions = [
    "本月回款差距主要来自哪些客户？",
    "两个延期项目分别卡在哪个里程碑？",
    "华东新增商机由谁负责？",
  ];

  return (
    <article className="executive-report executive-report-daily">
      <header className="executive-report-lead">
        <div className="executive-report-meta">
          <div><span>每日经营变化</span><time dateTime="2026-07-26">2026.07.26</time></div>
          <p>数据截至 7月25日 02:06 · 今日 05:03 生成</p>
        </div>
        <h1>经营节奏总体稳定，<br />回款和两项交付偏差需要今天确认。</h1>
        <p>基于最近两次成功快照，仅展示值得关注的变化。</p>
      </header>

      {feishuPreview && <FeishuPreview type="daily" />}

      <section className="executive-metric-rail" aria-label="今日关键指标">
        {metrics.map((metric) => <ExecutiveReportMetric key={metric.label} {...metric} />)}
      </section>

      <section className="executive-report-section" aria-labelledby="daily-changes-title">
        <header><span>01—03</span><h2 id="daily-changes-title">今日关键变化</h2></header>
        <div className="executive-change-list">
          {dailyChanges.map((change, index) => (
            <button type="button" className="executive-change-row" key={change.title} onClick={() => onQuestion(questions[index])}>
              <span className="executive-change-index">{String(index + 1).padStart(2, "0")}</span>
              <span className={`executive-change-status ${change.tone}`}>{change.state}</span>
              <span className="executive-change-copy"><strong>{change.title}</strong><small>{change.detail}</small></span>
              <span className="executive-change-arrow" aria-hidden="true">→</span>
            </button>
          ))}
        </div>
      </section>

      <section className="executive-action-strip" aria-labelledby="daily-actions-title">
        <header><span>需要关注</span><h2 id="daily-actions-title">今天需要确认</h2></header>
        <ol>
          <li><span>1</span><strong>确认三笔逾期回款的最新承诺日期</strong></li>
          <li><span>2</span><strong>锁定两个延期项目的客户确认与资源排期</strong></li>
        </ol>
        <button type="button" onClick={() => onQuestion(questions[0])}>继续追问 <span aria-hidden="true">→</span></button>
      </section>

      <ReportProvenance scope="2026-07-25，全部事业部" sources="商机主表、项目交付标准表、经营财务与回款表" definition="回款进度按本月计划口径；变化基于最近两次成功快照。" />
      <ReportFollowUps questions={questions} onQuestion={onQuestion} />
    </article>
  );
}

export function WeeklyBriefView({ feishuPreview, onQuestion }: { feishuPreview: boolean; onQuestion: (question: string) => void }) {
  const sections = [
    ["目标完成与差距", "收入完成 77.6%，较上一完整自然周提高 4.2 个百分点。"],
    ["商机与签约", "新增两笔高概率商机，一笔预计签约日延后至 8月。"],
    ["重点客户与项目", "云海智造验收与回款叠加，北陆能源签约时间需复核。"],
    ["项目交付", "15 个项目按计划，2 个里程碑存在偏差。"],
    ["收入、毛利与回款", "毛利率保持稳定，回款差距较上一周扩大 3.1 个百分点。"],
  ];
  const metrics: Array<{ label: string; value: string; note: string; tone: Tone }> = [
    { label: "收入完成", value: "77.6%", note: "周环比 +4.2 个百分点", tone: "positive" },
    { label: "新增加权商机", value: "1,180万", note: "2 笔高概率", tone: "positive" },
    { label: "回款完成", value: "65.9%", note: "低于周计划 10.4 个百分点", tone: "risk" },
    { label: "交付关注", value: "2 个", note: "其余 15 个正常", tone: "attention" },
  ];
  const questions = ["第30周回款差距来自哪些客户？", "对比前两周的商机变化。", "整理成周一经营会提纲。"];

  return (
    <article className="executive-report executive-report-weekly">
      <header className="executive-report-lead">
        <div className="executive-report-meta">
          <div><span>每周高层经营简报</span><time dateTime="2026-W30">第30周</time></div>
          <p>2026.07.13—07.19 · 7月20日 06:02 生成</p>
        </div>
        <h1>签约质量改善，<br />但回款与交付节奏仍需校准。</h1>
        <p>对比上一完整自然周，并同时参考本月目标进度；不将不完整周与完整周直接比较。</p>
      </header>

      {feishuPreview && <FeishuPreview type="weekly" />}

      <section className="executive-metric-rail weekly" aria-label="本周关键指标">
        {metrics.map((metric) => <ExecutiveReportMetric key={metric.label} {...metric} />)}
      </section>

      <section className="executive-report-section" aria-labelledby="weekly-judgements-title">
        <header><span>01—05</span><h2 id="weekly-judgements-title">本周经营判断</h2></header>
        <div className="executive-change-list weekly">
          {sections.map(([title, body], index) => (
            <button type="button" className="executive-change-row" key={title} onClick={() => onQuestion(index === 1 ? questions[1] : index === 4 ? questions[0] : questions[2])}>
              <span className="executive-change-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="executive-change-copy"><strong>{title}</strong><small>{body}</small></span>
              <span className="executive-change-arrow" aria-hidden="true">→</span>
            </button>
          ))}
        </div>
      </section>

      <section className="executive-action-strip weekly" aria-labelledby="weekly-actions-title">
        <header><span>需要关注</span><h2 id="weekly-actions-title">下周优先事项</h2></header>
        <ol>
          <li><span>1</span><strong>将三笔逾期记录落实到责任人与明确日期</strong></li>
          <li><span>2</span><strong>在周中前锁定客户验收与联调资源</strong></li>
          <li><span>3</span><strong>保持两笔新增商机的关键人沟通节奏</strong></li>
        </ol>
        <button type="button" onClick={() => onQuestion(questions[2])}>整理经营会提纲 <span aria-hidden="true">→</span></button>
      </section>

      <ReportProvenance scope="2026-07-13 至 2026-07-19，全部事业部" sources="商机主表、项目交付标准表、经营财务与回款表" definition="周环比只比较两个完整自然周，同时参考本月目标进度。" />
      <ReportFollowUps questions={questions} onQuestion={onQuestion} />
    </article>
  );
}

export function ExecutiveReportMetric({ label, value, note, tone }: { label: string; value: string; note: string; tone: Tone }) {
  return <div className={`executive-report-metric ${tone}`}><span>{label}</span><strong>{value}</strong><small><i aria-hidden="true" />{note}</small></div>;
}

export function ReportProvenance({ scope, sources, definition }: { scope: string; sources: string; definition: string }) {
  return (
    <details className="executive-report-provenance">
      <summary>数据范围、来源与指标口径</summary>
      <dl>
        <div><dt>范围</dt><dd>{scope}</dd></div>
        <div><dt>来源</dt><dd>{sources}</dd></div>
        <div><dt>口径</dt><dd>{definition}</dd></div>
      </dl>
    </details>
  );
}

export function ReportFollowUps({ questions, onQuestion }: { questions: string[]; onQuestion: (question: string) => void }) {
  return <section className="executive-report-followups" aria-label="下一步可以询问"><span>下一步可以询问</span><div>{questions.map((question) => <button type="button" key={question} onClick={() => onQuestion(question)}>{question}<i aria-hidden="true">→</i></button>)}</div></section>;
}

export function FeishuPreview({ type }: { type: "daily" | "weekly" }) {
  return <aside className="feishu-preview" aria-label="飞书消息样例"><header><span className="feishu-mark" aria-hidden="true">飞</span><div><strong>AI 秘书经营提醒</strong><small>今天 07:30 · 已去重</small></div></header><div><h3>{type === "daily" ? "每日经营变化｜7月26日" : "每周高层经营简报｜第30周"}</h3><p>{type === "daily" ? "经营节奏总体稳定，回款和两项交付偏差需要今天确认。" : "签约质量改善，但回款与交付节奏仍需校准。"}</p><ol><li>回款进度低于计划</li><li>两个项目进入延期关注</li><li>华东新增高概率商机</li></ol><small>数据截至 2026-07-25 02:06</small><a href={type === "daily" ? "?view=daily" : "?view=weekly"}>进入 AI 秘书继续查看</a></div><footer>未登录时先完成登录，再返回本内容。</footer></aside>;
}

export function CapabilitiesView({ onBack, language }: { onBack: () => void; language: UiLanguage }) {
  const domains = [
    ["商机", "已接入", "2026-01-01 至 2026-07-25", "金额、阶段、概率、预计签约日、客户、负责人"],
    ["项目交付", "演示数据", "2026-04-01 至 2026-07-25", "进度、计划、里程碑、预计完成、负责人"],
    ["财务与回款", "演示数据", "2026-04-01 至 2026-07-25", "收入、毛利、应收、未回、计划回款日"],
    ["每日变化快照", "已生成", "最近 7 个完整自然日", "新增、更新、推进、赢单、延期与回款变化"],
  ];
  return <div className="page subpage capabilities-page"><section className="page-heading"><button type="button" className="back-link" onClick={onBack}>返回首页</button><p className="eyebrow">自然语言范围说明</p><h1>当前可查询范围</h1><p>这里展示已接入的数据、可选组织和数据时间，不显示数据库表名。</p></section><section className="capability-domain-list"><header className="section-header"><div><p className="eyebrow">4 个数据域</p><h2>已接入能力</h2></div><span>最新数据 7月25日 02:06</span></header>{domains.map(([name, status, range, metrics]) => <article key={name}><div><h3>{name}</h3><StatusBadge tone={status === "已接入" || status === "已生成" ? "positive" : "attention"} label={status} /></div><dl><div><dt>可查询时间</dt><dd>{range}</dd></div><div><dt>可用指标</dt><dd>{metrics}</dd></div></dl></article>)}</section><section className="organization-scope"><p className="eyebrow">组织范围</p><h2>可选组织</h2><div>{availableOrganizations.map((organization) => <span key={organization.id}>{organization.labels[language]}</span>)}</div><p>可选范围由管理端配置，只有已接入且状态可用的事业部才会在高层端出现。</p></section><section className="data-gap-table"><p className="eyebrow">缺口影响</p><h2>数据缺失时会明确说明</h2><div className="table-wrap"><table><thead><tr><th>缺少数据</th><th>无法稳定回答</th></tr></thead><tbody><tr><td>目标</td><td>完成率、差距和目标进度</td></tr><tr><td>商机金额或阶段</td><td>商机规模、漏斗和预测</td></tr><tr><td>项目计划与进度</td><td>延期、里程碑和交付判断</td></tr><tr><td>应收与回款日期</td><td>逾期、账龄和回款风险</td></tr><tr><td>每日快照</td><td>变化原因和每日摘要</td></tr></tbody></table></div></section></div>;
}

export function AccountView({ memoryEnabled, onMemory, onLogout }: { memoryEnabled: boolean; onMemory: () => void; onLogout: () => void }) {
  return <div className="page subpage account-page"><section className="page-heading"><p className="eyebrow">个人设置</p><h1>账号与推送</h1><p>高层端只展示个人可控信息，不开放模型和数据源配置。</p></section><section className="account-grid"><article><p className="eyebrow">账号</p><h2>董事长</h2><dl><div><dt>账号</dt><dd>chairman</dd></div><div><dt>组织范围</dt><dd>全部事业部</dd></div><div><dt>最近登录</dt><dd>今天 08:18 · 当前设备</dd></div><div><dt>会话状态</dt><dd><StatusBadge tone="positive" label="有效" /></dd></div></dl><button type="button" className="danger-text-button" onClick={onLogout}>退出当前账号</button></article><article><p className="eyebrow">飞书提醒</p><h2>当前推送时间</h2><dl><div><dt>每日经营变化</dt><dd>每天 07:30</dd></div><div><dt>每周高层简报</dt><dd>周一 07:45</dd></div><div><dt>管理方式</dt><dd>由企业管理员配置</dd></div></dl><a href="mailto:admin@example.invalid">申请调整或关闭</a></article><article><p className="eyebrow">长期记忆</p><h2>{memoryEnabled ? "已开启" : "已关闭"}</h2><p>您可以查看、修改、删除或清空系统保存的稳定偏好。</p><button type="button" className="secondary-button" onClick={onMemory}>管理个人记忆</button></article></section></div>;
}

export function ScopePanel({ scope, language, onClose, onSave }: { scope: ScopeState; language: UiLanguage; onClose: () => void; onSave: (scope: ScopeState) => void }) {
  const [draft, setDraft] = useState(scope);
  function toggleScopeOrganization(organizationId: string) {
    setDraft((current) => ({ ...current, organizationIds: toggleOrganizationSelection(current.organizationIds, organizationId) }));
  }
  return <div className="overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><aside className="side-panel scope-side-panel" role="dialog" aria-modal="true" aria-labelledby="scope-title"><header><div><p className="eyebrow">仅影响后续问题</p><h2 id="scope-title">当前会话范围</h2></div><button type="button" onClick={onClose} aria-label="关闭范围设置">关闭</button></header><div className="panel-body"><label className="field"><span>时间范围</span><select value={draft.time} onChange={(event) => setDraft({ ...draft, time: event.target.value })}><option>本月累计</option><option>本周截至最新数据</option><option>上一个完整自然周</option><option>最近七个完整自然日</option><option>本季度</option></select></label><fieldset><legend>组织范围</legend><div className="choice-grid">{availableOrganizations.map((organization) => <label key={organization.id} className={draft.organizationIds.includes(organization.id) ? "selected" : ""}><input type="checkbox" checked={draft.organizationIds.includes(organization.id)} onChange={() => toggleScopeOrganization(organization.id)} /><span>{organization.labels[language]}</span></label>)}</div><small className="scope-admin-note">仅展示管理端已配置并完成数据接入的事业部。</small></fieldset><label className="field"><span>负责人，可选</span><select value={draft.owner} onChange={(event) => setDraft({ ...draft, owner: event.target.value })}><option value="">全部负责人</option>{owners.map((owner) => <option key={owner}>{owner}</option>)}</select></label><label className="field"><span>当前对象，可选</span><input value={draft.object} onChange={(event) => setDraft({ ...draft, object: event.target.value })} placeholder="例如：云海智造或升级项目" /></label></div><footer><button type="button" className="text-button" onClick={() => setDraft({ time: "本月累计", organizationIds: [ALL_ORGANIZATIONS_ID], owner: "", object: "" })}>清除并恢复默认</button><button type="button" className="primary-button" onClick={() => onSave(draft)}>保存范围</button></footer></aside></div>;
}

export function DemoDrawer({ onClose, onRun }: { onClose: () => void; onRun: (id: number) => void }) {
  return <div className="overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><aside className="side-panel demo-drawer" role="dialog" aria-modal="true" aria-labelledby="demo-title"><header><div><p className="eyebrow">功能说明书第22章</p><h2 id="demo-title">十个标准演示场景</h2></div><button type="button" onClick={onClose}>关闭</button></header><div className="demo-list">{demoScenarios.map((scenario) => <button type="button" key={scenario.id} onClick={() => onRun(scenario.id)}><span>{String(scenario.id).padStart(2, "0")}</span><span><strong>{scenario.title}</strong><small>{scenario.description}</small></span><span aria-hidden="true">→</span></button>)}</div><footer><p>每个场景使用固定演示样本，便于连续讲解与验收。</p></footer></aside></div>;
}

export function AdminWorkspace({ onLogout }: { onLogout: () => void }) {
  const [section, setSection] = useState<AdminSection>("overview");
  const [toast, setToast] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(""), 2600); return () => window.clearTimeout(timer); }, [toast]);
  const notify = (message: string) => setToast(message);
  return <div className="product-shell admin-shell"><a className="skip-link" href="#admin-main">跳到主要内容</a><header className="app-header"><button type="button" className="brand-button" onClick={() => setSection("overview")}><span className="brand-glyph admin" aria-hidden="true">管</span><span><strong>AI 秘书管理端</strong><small>企业管理员与 FDE</small></span></button><nav className="primary-nav admin-nav" aria-label="管理端主导航">{adminNavigation.map((item) => <button type="button" key={item.id} className={section === item.id ? "active" : ""} aria-current={section === item.id ? "page" : undefined} onClick={() => setSection(item.id)}>{item.label}</button>)}</nav><div className="profile-control"><button type="button" className="profile-button" aria-label="打开管理员菜单" aria-expanded={profileOpen} onClick={() => setProfileOpen((current) => !current)}><span aria-hidden="true">管</span><span><strong>企业管理员</strong><small>配置权限</small></span></button>{profileOpen && <div className="profile-menu"><button type="button" onClick={() => setSection("account")}>高层账号管理</button><button type="button" onClick={onLogout}>退出管理端</button></div>}</div></header><main id="admin-main" className="app-main admin-main">{section === "overview" && <AdminOverview onNavigate={setSection} />}{section === "account" && <AdminAccount onBack={() => setSection("overview")} onNotify={notify} />}{section === "model" && <AdminModel onNotify={notify} />}{section === "source" && <AdminSource onNotify={notify} />}{section === "automation" && <AdminAutomation onNotify={notify} />}{section === "feishu" && <AdminFeishu onNotify={notify} />}{section === "capability" && <AdminCapabilities onNotify={notify} />}{section === "runtime" && <AdminRuntime onNotify={notify} />}</main><nav className="mobile-nav admin-mobile-nav" aria-label="管理端移动导航">{adminNavigation.map((item) => <button type="button" key={item.id} className={section === item.id ? "active" : ""} onClick={() => setSection(item.id)}><span>{item.short.slice(0, 1)}</span>{item.short}</button>)}</nav>{toast && <Toast message={toast} />}</div>;
}

export function AdminOverview({ onNavigate }: { onNavigate: (section: AdminSection) => void }) {
  const statuses: Array<[string, string, Tone, AdminSection, string]> = [
    ["H5 服务", "运行正常", "positive", "runtime", "刚刚检查"], ["Hermes Agent", "运行正常", "positive", "runtime", "Worker 心跳 28 秒前"], ["当前模型", "Qwen3-32B", "positive", "model", "连接测试 842ms"], ["企业数据库", "只读连接正常", "positive", "source", "最近同步 02:06"], ["飞书同步", "运行正常", "positive", "source", "读取 1,286 条"], ["自动任务", "1 项关注", "attention", "automation", "一次推送待重试"],
  ];
  return <div className="page subpage admin-page"><section className="page-heading split"><div><p className="eyebrow">系统总览</p><h1>六项核心状态</h1><p>这里只展示可操作摘要，完整日志和高层会话正文不会出现在总览。</p></div><span className="last-check">最近检查 09:16:24</span></section><section className="admin-status-grid">{statuses.map(([name, status, tone, target, detail], index) => <button type="button" key={name} onClick={() => onNavigate(target)}><span className="status-index">0{index + 1}</span><div><small>{name}</small><strong>{status}</strong><span>{detail}</span></div><StatusBadge tone={tone} label={tone === "positive" ? "正常" : "关注"} /></button>)}</section><div className="admin-overview-grid"><section><header className="section-header"><div><p className="eyebrow">最近任务</p><h2>运行记录</h2></div><button type="button" className="text-button" onClick={() => onNavigate("automation")}>查看任务</button></header><div className="simple-list"><div><time>05:03</time><span><strong>每日经营摘要</strong><small>使用 02:06 成功快照生成</small></span><StatusBadge tone="positive" label="成功" /></div><div><time>02:06</time><span><strong>经营数据同步</strong><small>读取 1,286 · 新增 14 · 更新 37</small></span><StatusBadge tone="positive" label="成功" /></div><div><time>07:30</time><span><strong>飞书摘要推送</strong><small>首次超时，等待单独重试</small></span><StatusBadge tone="attention" label="待重试" /></div></div></section><section><header className="section-header"><div><p className="eyebrow">账号</p><h2>高层用户</h2></div><button type="button" className="text-button" onClick={() => onNavigate("account")}>管理账号</button></header><dl className="overview-account"><div><dt>账号</dt><dd>chairman</dd></div><div><dt>状态</dt><dd><StatusBadge tone="positive" label="已启用" /></dd></div><div><dt>最近登录</dt><dd>今天 08:18</dd></div><div><dt>管理员审计权限</dt><dd>未启用</dd></div></dl></section></div></div>;
}

export function AdminAccount({ onBack, onNotify }: { onBack: () => void; onNotify: (message: string) => void }) {
  const [enabled, setEnabled] = useState(true);
  return <div className="page subpage admin-page"><section className="page-heading"><button type="button" className="back-link" onClick={onBack}>返回总览</button><p className="eyebrow">首版单账号</p><h1>高层账号管理</h1><p>管理员不能查看高层完整会话、长期记忆或上传文件正文。</p></section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">当前账号</p><h2>董事长</h2></div><StatusBadge tone={enabled ? "positive" : "attention"} label={enabled ? "已启用" : "已停用"} /></header><div className="settings-grid"><label className="field"><span>账号</span><input value="chairman" readOnly /></label><label className="field"><span>临时密码</span><input value="••••••••••" readOnly /></label><label className="field"><span>创建时间</span><input value="2026-06-18 10:20" readOnly /></label><label className="field"><span>最近登录</span><input value="2026-07-26 08:18" readOnly /></label></div><div className="settings-actions"><button type="button" className="secondary-button" onClick={() => { setEnabled((current) => !current); onNotify(enabled ? "账号已停用" : "账号已启用"); }}>{enabled ? "停用账号" : "启用账号"}</button><button type="button" className="secondary-button" onClick={() => onNotify("临时密码已重置，首次登录必须修改")}>重置密码</button><button type="button" className="danger-text-button" onClick={() => onNotify("全部登录会话已失效")}>失效全部登录会话</button></div></section><aside className="privacy-note"><strong>默认隐私边界</strong><p>企业管理员只能管理账号状态，不能直接读取高层会话、长期记忆和文件正文。如需审计权限，必须单独配置并明确告知高层用户。</p></aside></div>;
}

export function AdminModel({ onNotify }: { onNotify: (message: string) => void }) {
  const [model, setModel] = useState("Qwen3-32B 本地模型");
  const [tested, setTested] = useState(true);
  const [testing, setTesting] = useState(false);
  function test() { setTesting(true); window.setTimeout(() => { setTesting(false); setTested(true); onNotify("连接测试通过，响应 842ms"); }, 850); }
  return <div className="page subpage admin-page"><section className="page-heading"><p className="eyebrow">一次只启用一个</p><h1>模型配置</h1><p>切换前必须通过连接测试。密钥保存后只显示掩码。</p></section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">当前配置</p><h2>经营助理主模型</h2></div><StatusBadge tone={tested ? "positive" : "attention"} label={tested ? "测试通过" : "等待测试"} /></header><div className="settings-grid"><label className="field"><span>配置名称</span><input defaultValue="经营助理主模型" /></label><label className="field"><span>模型类型</span><select defaultValue="本地大模型"><option>云端大模型</option><option>本地大模型</option><option>本地小模型</option></select></label><label className="field wide"><span>API Base URL</span><input defaultValue="http://model-gateway:8000/v1" /></label><label className="field"><span>API Key</span><input type="password" value="sk-demo-masked-key" readOnly /></label><label className="field"><span>模型名称</span><select value={model} onChange={(event) => { setModel(event.target.value); setTested(false); }}><option>Qwen3-32B 本地模型</option><option>云端兼容模型</option><option>Qwen3-8B 本地小模型</option></select></label><label className="field"><span>超时时间</span><input type="number" defaultValue="120" /></label><label className="field"><span>最大输出长度</span><input type="number" defaultValue="8192" /></label><label className="field"><span>温度，可选</span><input type="number" step="0.1" defaultValue="0.2" /></label></div><div className="settings-actions"><button type="button" className="secondary-button" onClick={test} disabled={testing}>{testing ? "正在测试" : "测试连接"}</button><button type="button" className="primary-button" disabled={!tested} onClick={() => onNotify(`${model} 已设为当前模型`)}>保存并设为当前模型</button></div><p className="settings-footnote">最近测试：2026-07-26 09:10 · 842ms · 返回格式正常</p></section></div>;
}

export function AdminSource({ onNotify }: { onNotify: (message: string) => void }) {
  const [tab, setTab] = useState<"connection" | "mapping" | "sync" | "simulation">("connection");
  const [mappingFixed, setMappingFixed] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const preview = [
    ["OPP-260721-03", "北陆能源二期", "方案确认", "2,400万", "沈澜"], ["OPP-260722-01", "澄川门店升级", "商务谈判", "1,680万", "陈岚"], ["OPP-260723-02", "启岳数据平台", "需求确认", "920万", "林序"], ["OPP-260724-04", "云海智造扩容", "方案确认", "1,260万", "唐昱"],
  ];
  function runSync() { setSyncing(true); window.setTimeout(() => { setSyncing(false); onNotify("同步完成：读取 1,286 条，新增 14 条，更新 37 条"); }, 950); }
  return <div className="page subpage admin-page"><section className="page-heading"><p className="eyebrow">飞书多维表格与标准数据</p><h1>数据源</h1><p>连接、字段映射、同步和模拟数据状态在一个流程中完成。</p></section><div className="subnav" role="tablist">{([ ["connection", "连接与预览"], ["mapping", "字段映射"], ["sync", "同步记录"], ["simulation", "模拟数据"] ] as const).map(([id, label]) => <button type="button" role="tab" key={id} aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</div>{tab === "connection" && <section className="settings-section"><header className="section-header"><div><p className="eyebrow">真实商机来源</p><h2>飞书多维表格</h2></div><StatusBadge tone="positive" label="已连接" /></header><div className="settings-grid"><label className="field"><span>飞书应用 ID</span><input defaultValue="cli_a7f••••••9c2" /></label><label className="field"><span>应用密钥</span><input type="password" value="feishu-masked-secret" readOnly /></label><label className="field"><span>Base Token</span><input defaultValue="bas_demo_2026" /></label><label className="field"><span>数据表 ID</span><input defaultValue="tbl_opportunity_main" /></label><label className="field"><span>视图 ID，可选</span><input defaultValue="vew_active_opportunities" /></label><label className="field"><span>同步时区</span><select defaultValue="Asia/Shanghai"><option>Asia/Shanghai</option></select></label></div><div className="settings-actions"><button type="button" className="secondary-button" onClick={() => onNotify("飞书连接正常，读取到 42 个字段")}>测试连接并读取字段</button><button type="button" className="primary-button" onClick={() => setTab("mapping")}>进入字段映射</button></div><div className="preview-table"><header><h3>前 20 条记录预览</h3><span>当前展示 4 条演示记录</span></header><div className="table-wrap"><table><thead><tr><th>商机编号</th><th>商机名称</th><th>阶段</th><th>金额</th><th>负责人</th></tr></thead><tbody>{preview.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div></div></section>}{tab === "mapping" && <section className="settings-section mapping-section"><header className="section-header"><div><p className="eyebrow">映射版本 V3 · 今天 09:02</p><h2>字段映射</h2></div><StatusBadge tone={mappingFixed ? "positive" : "risk"} label={mappingFixed ? "校验完整" : "1 个必需字段缺失"} /></header><div className="table-wrap"><table><thead><tr><th>源字段</th><th>标准字段</th><th>校验结果</th><th>影响问题</th></tr></thead><tbody><tr><td>商机金额</td><td><select defaultValue="opportunity_amount"><option value="opportunity_amount">商机金额</option></select></td><td><StatusBadge tone="positive" label="完整" /></td><td>商机规模、预测</td></tr><tr><td>当前阶段</td><td><select defaultValue="stage"><option value="stage">商机阶段</option></select></td><td><StatusBadge tone="positive" label="完整" /></td><td>漏斗、推进变化</td></tr><tr><td>{mappingFixed ? "计划回款日" : "未映射"}</td><td><select value={mappingFixed ? "planned_collection_date" : ""} onChange={(event) => setMappingFixed(Boolean(event.target.value))}><option value="">请选择源字段</option><option value="planned_collection_date">计划回款日</option></select></td><td><StatusBadge tone={mappingFixed ? "positive" : "risk"} label={mappingFixed ? "完整" : "缺失"} /></td><td>逾期、账龄、回款风险</td></tr><tr><td>业务负责人</td><td><select defaultValue="owner"><option value="owner">负责人</option></select></td><td><StatusBadge tone="positive" label="完整" /></td><td>组织与负责人比较</td></tr></tbody></table></div>{!mappingFixed && <p className="form-error">必需字段“计划回款日”缺失，正式同步不能启用。回款与现金风险问题将无法稳定回答。</p>}<div className="settings-actions"><button type="button" className="secondary-button" onClick={() => onNotify("映射配置已导出，未包含凭证")}>导出映射配置</button><button type="button" className="primary-button" disabled={!mappingFixed} onClick={() => { onNotify("映射版本 V4 已保存"); setTab("sync"); }}>保存并启用同步</button></div></section>}{tab === "sync" && <section className="settings-section"><header className="section-header"><div><p className="eyebrow">最近成功 7月25日 02:06</p><h2>数据同步</h2></div><button type="button" className="primary-button" onClick={runSync} disabled={syncing}>{syncing ? "正在同步" : "手动同步"}</button></header><section className="sync-metrics"><Metric label="读取记录" value="1,286" note="最近一次任务" tone="neutral" /><Metric label="新增" value="14" note="较上一快照" tone="positive" /><Metric label="更新" value="37" note="已写入标准表" tone="neutral" /><Metric label="失败" value="0" note="无需重试" tone="positive" /></section><div className="simple-list"><div><time>7月25日 02:06</time><span><strong>每日定时同步</strong><small>最近数据时间 7月25日 01:58</small></span><StatusBadge tone="positive" label="成功" /></div><div><time>7月24日 02:04</time><span><strong>每日定时同步</strong><small>首次字段校验失败，重试后成功</small></span><button type="button" onClick={() => onNotify("失败摘要：计划回款日字段短暂不可读")}>失败摘要</button></div></div><p className="settings-footnote">管理端只读同步，不允许直接编辑飞书源数据。</p></section>}{tab === "simulation" && <section className="settings-section"><header className="section-header"><div><p className="eyebrow">固定演示版本</p><h2>模拟数据状态</h2></div><span>生成时间 2026-07-18 11:20</span></header><div className="simulation-list"><article><div><h3>商机</h3><p>来自飞书多维表格真实连接</p></div><StatusBadge tone="positive" label="真实来源" /></article><article><div><h3>项目交付</h3><p>与赢单商机、客户和负责人建立关联</p></div><StatusBadge tone="attention" label="模拟 V2026.07" /></article><article><div><h3>经营财务与回款</h3><p>与项目、客户和计划回款日建立关联</p></div><StatusBadge tone="attention" label="模拟 V2026.07" /></article></div><aside className="privacy-note"><strong>重建控制</strong><p>模拟数据生成与重置只通过 FDE 部署工具执行，企业管理员不能在演示过程中随意重建。</p></aside></section>}</div>;
}

export function AdminAutomation({ onNotify }: { onNotify: (message: string) => void }) {
  const [syncTime, setSyncTime] = useState("02:00"); const [dailyTime, setDailyTime] = useState("05:00"); const [dailyPush, setDailyPush] = useState("07:30"); const [weeklyTime, setWeeklyTime] = useState("06:00"); const [weeklyPush, setWeeklyPush] = useState("07:45"); const [pushEnabled, setPushEnabled] = useState(true);
  const conflict = dailyTime <= syncTime || dailyPush <= dailyTime || weeklyPush <= weeklyTime;
  return <div className="page subpage admin-page"><section className="page-heading"><p className="eyebrow">生成与推送分离</p><h1>自动任务</h1><p>生成任务必须晚于数据同步，推送失败不会重新生成内容。</p></section><div className="automation-grid"><section className="settings-section"><header className="section-header"><div><p className="eyebrow">每天</p><h2>每日经营变化</h2></div><StatusBadge tone={pushEnabled ? "positive" : "attention"} label={pushEnabled ? "已启用" : "仅生成不推送"} /></header><div className="settings-grid one-column"><label className="field"><span>数据同步时间</span><input type="time" value={syncTime} onChange={(event) => setSyncTime(event.target.value)} /></label><label className="field"><span>摘要生成时间</span><input type="time" value={dailyTime} onChange={(event) => setDailyTime(event.target.value)} /></label><label className="field"><span>飞书推送时间</span><input type="time" value={dailyPush} onChange={(event) => setDailyPush(event.target.value)} /></label><label className="check-row"><input type="checkbox" checked={pushEnabled} onChange={(event) => setPushEnabled(event.target.checked)} /><span><strong>启用每日飞书推送</strong><small>关闭后摘要仍保存在 H5</small></span></label></div><p className="next-run">下一次执行：7月27日 {syncTime} 同步，{dailyTime} 生成，{dailyPush} 推送</p></section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">每周一</p><h2>每周高层简报</h2></div><StatusBadge tone="positive" label="已启用" /></header><div className="settings-grid one-column"><label className="field"><span>生成星期</span><select defaultValue="周一"><option>周一</option></select></label><label className="field"><span>简报生成时间</span><input type="time" value={weeklyTime} onChange={(event) => setWeeklyTime(event.target.value)} /></label><label className="field"><span>飞书推送时间</span><input type="time" value={weeklyPush} onChange={(event) => setWeeklyPush(event.target.value)} /></label></div><p className="next-run">下一次执行：7月27日 {weeklyTime} 生成，{weeklyPush} 推送</p></section></div>{conflict && <p className="form-error task-conflict">时间配置冲突：生成必须晚于同步，推送必须晚于对应内容生成。</p>}<section className="settings-section"><header className="section-header"><div><p className="eyebrow">最近运行</p><h2>任务记录</h2></div><button type="button" className="primary-button" disabled={conflict} onClick={() => onNotify("自动任务配置已保存，下一次执行时间已更新")}>保存配置</button></header><div className="simple-list"><div><time>今日 05:03</time><span><strong>每日摘要</strong><small>数据同步成功后生成</small></span><button type="button" onClick={() => onNotify("正在使用最新成功快照重新生成")}>重新运行</button></div><div><time>今日 07:30</time><span><strong>飞书推送</strong><small>首次请求超时，内容已保留</small></span><button type="button" onClick={() => onNotify("只重试推送，不重新生成内容")}>重试推送</button></div></div></section></div>;
}

export function AdminFeishu({ onNotify }: { onNotify: (message: string) => void }) {
  const [testing, setTesting] = useState(false);
  function test() { setTesting(true); window.setTimeout(() => { setTesting(false); onNotify("测试消息发送成功"); }, 850); }
  return <div className="page subpage admin-page"><section className="page-heading"><p className="eyebrow">只推送每日与每周内容</p><h1>飞书推送</h1><p>实时预警、营销通知和普通系统消息不在首版范围。</p></section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">连接配置</p><h2>飞书应用</h2></div><StatusBadge tone="positive" label="已连接" /></header><div className="settings-grid"><label className="field"><span>飞书应用 ID</span><input defaultValue="cli_a7f••••••9c2" /></label><label className="field"><span>应用密钥</span><input type="password" value="feishu-masked-secret" readOnly /></label><label className="field"><span>接收用户 Open ID</span><input defaultValue="ou_demo_chairman_01" /></label><label className="field"><span>H5 外部访问地址</span><input defaultValue="https://chairman-assistant.example.invalid" /></label><label className="field wide"><span>消息模板</span><select defaultValue="高层经营摘要 V1"><option>高层经营摘要 V1</option></select></label></div><div className="settings-actions"><button type="button" className="secondary-button" onClick={test} disabled={testing}>{testing ? "正在发送" : "测试发送"}</button><button type="button" className="primary-button" onClick={() => onNotify("飞书推送配置已保存")}>保存配置</button></div></section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">去重记录</p><h2>最近推送</h2></div></header><div className="simple-list"><div><time>今日 07:30</time><span><strong>每日经营变化｜7月26日</strong><small>首次超时，摘要仍保存在 H5</small></span><button type="button" onClick={() => onNotify("推送重试成功，内容不会再次发送")}>重试</button></div><div><time>7月20日 07:45</time><span><strong>每周高层经营简报｜第30周</strong><small>消息 ID fs_20260720_week30</small></span><StatusBadge tone="positive" label="已送达" /></div></div></section></div>;
}

export function AdminCapabilities({ onNotify }: { onNotify: (message: string) => void }) {
  const [tab, setTab] = useState<"whitelist" | "search">("whitelist");
  const [searchEnabled, setSearchEnabled] = useState(true);
  const [tools, setTools] = useState([
    ["经营总览查询", "1.3.0", "内置", "经营数据", true, "通过"], ["商机与预测", "1.2.4", "企业", "经营数据", true, "通过"], ["项目交付查询", "1.1.8", "企业", "经营数据", true, "通过"], ["回款与现金", "1.0.9", "企业", "经营数据", true, "通过"], ["当前会话文档", "2.0.1", "内置", "文件", true, "通过"], ["公开搜索", "1.4.2", "Anspire", "泛化", true, "842ms"],
  ] as Array<[string, string, string, string, boolean, string]>);
  return <div className="page subpage admin-page"><section className="page-heading"><p className="eyebrow">受控暴露</p><h1>能力白名单</h1><p>FDE 可以启停已安装能力，不能通过界面上传任意代码。</p></section><div className="subnav"> <button type="button" className={tab === "whitelist" ? "active" : ""} onClick={() => setTab("whitelist")}>Skills 与 MCP</button><button type="button" className={tab === "search" ? "active" : ""} onClick={() => setTab("search")}>Anspire 搜索</button></div>{tab === "whitelist" ? <section className="settings-section"><header className="section-header"><div><p className="eyebrow">已安装 6 项</p><h2>启停控制</h2></div><button type="button" className="primary-button" onClick={() => onNotify("白名单已保存，未启用工具不会暴露给执行环境")}>保存白名单</button></header><div className="table-wrap"><table><thead><tr><th>能力</th><th>版本 / 来源</th><th>适用范围</th><th>最近测试</th><th>状态</th></tr></thead><tbody>{tools.map((tool, index) => <tr key={tool[0]}><td><strong>{tool[0]}</strong></td><td>{tool[1]} · {tool[2]}</td><td>{tool[3]}</td><td>{tool[5]}</td><td><label className="switch compact"><input type="checkbox" checked={tool[4]} onChange={(event) => setTools((current) => current.map((item, itemIndex) => itemIndex === index ? [item[0], item[1], item[2], item[3], event.target.checked, item[5]] : item))} /><span aria-hidden="true" /><small>{tool[4] ? "启用" : "停用"}</small></label></td></tr>)}</tbody></table></div></section> : <section className="settings-section"><header className="section-header"><div><p className="eyebrow">公开研究</p><h2>Anspire 搜索</h2></div><StatusBadge tone={searchEnabled ? "positive" : "attention"} label={searchEnabled ? "已启用" : "已停用"} /></header><div className="settings-grid"><label className="field"><span>API Key</span><input type="password" value="anspire-masked-key" readOnly /></label><label className="field"><span>默认搜索</span><select defaultValue="标准搜索"><option>标准搜索</option><option>PRO 搜索</option></select></label><label className="field"><span>默认返回条数</span><input type="number" defaultValue="8" /></label><label className="field"><span>超时时间</span><input type="number" defaultValue="45" /></label></div><label className="check-row"><input type="checkbox" checked={searchEnabled} onChange={(event) => setSearchEnabled(event.target.checked)} /><span><strong>启用公开搜索</strong><small>停用后，行业研究问题会明确提示不可用</small></span></label><div className="settings-actions"><button type="button" className="secondary-button" onClick={() => onNotify("搜索测试通过，返回 8 条公开结果")}>测试搜索</button><button type="button" className="primary-button" onClick={() => onNotify("Anspire 配置已保存")}>保存配置</button></div><aside className="privacy-note"><strong>搜索脱敏</strong><p>内部金额、客户名、合同信息和文件正文不会发送到公开搜索接口。</p></aside></section>}</div>;
}

export function AdminRuntime({ onNotify }: { onNotify: (message: string) => void }) {
  const runtime = [
    ["Hermes 版本", "固定镜像 0.9.4", "positive"], ["当前模型", "Qwen3-32B 本地模型", "positive"], ["数据库连接", "只读连接正常", "positive"], ["经营数据工具", "11 个只读工具", "positive"], ["Worker 心跳", "28 秒前", "positive"], ["最近备份", "今日 03:10", "positive"], ["最近错误", "飞书推送超时 1 次", "attention"],
  ] as Array<[string, string, Tone]>;
  function downloadReport() {
    const payload = JSON.stringify({ generated_at: "2026-07-26T09:16:24+08:00", hermes_version: "0.9.4", model: "Qwen3-32B local", database: "healthy", secrets: "redacted", executive_messages: "excluded", latest_error: "feishu push timeout" }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "ai-secretary-diagnostic-redacted.json"; anchor.click(); URL.revokeObjectURL(url); onNotify("脱敏诊断报告已下载");
  }
  return <div className="page subpage admin-page"><section className="page-heading split"><div><p className="eyebrow">部署版本 demo-2026.07.26</p><h1>运行状态</h1><p>诊断信息不包含完整密钥、Prompt 或高层消息正文。</p></div><div className="heading-actions"><button type="button" className="secondary-button" onClick={() => onNotify("健康检查完成，6 项正常，1 项关注")}>立即健康检查</button><button type="button" className="primary-button" onClick={downloadReport}>下载脱敏诊断</button></div></section><section className="runtime-grid">{runtime.map(([label, value, tone]) => <article key={label}><small>{label}</small><strong>{value}</strong><StatusBadge tone={tone} label={tone === "positive" ? "正常" : "关注"} /></article>)}</section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">最近错误摘要</p><h2>可恢复问题</h2></div></header><div className="error-summary"><span className="status-dot attention" /><div><strong>飞书推送请求超时</strong><p>内容已在 H5 保存，可只重试推送。同一内容成功后不会重复发送。</p><dl><div><dt>发生时间</dt><dd>今天 07:30</dd></div><div><dt>错误标识</dt><dd>push_timeout_redacted</dd></div><div><dt>关联内容</dt><dd>每日经营变化｜7月26日</dd></div></dl></div><button type="button" className="secondary-button" onClick={() => onNotify("推送重试成功")}>重试推送</button></div></section><section className="settings-section"><header className="section-header"><div><p className="eyebrow">审计摘要</p><h2>最近路由记录</h2></div><span>不含用户消息正文</span></header><div className="simple-list"><div><time>09:12:06</time><span><strong>经营数据</strong><small>范围完整，调用只读数据能力</small></span><StatusBadge tone="positive" label="完成" /></div><div><time>09:08:42</time><span><strong>当前会话文件</strong><small>限定当前会话 1 个文件</small></span><StatusBadge tone="positive" label="完成" /></div><div><time>08:56:18</time><span><strong>公开研究</strong><small>脱敏检查通过</small></span><StatusBadge tone="positive" label="完成" /></div></div></section></div>;
}

export function ProjectDialog({
  state,
  project,
  onClose,
  onSave,
}: {
  state: ProjectDialogState;
  project: SidebarProject | null;
  onClose: () => void;
  onSave: (title: string, description: string) => string | null;
}) {
  const [title, setTitle] = useState(project?.title ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [error, setError] = useState("");
  const dialogRef = useRef<HTMLElement>(null);
  const editing = state.mode === "edit";

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLInputElement>("input")?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), textarea:not([disabled])"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) {
      setError("请输入项目名称。");
      return;
    }
    const validationError = onSave(nextTitle, description.trim());
    if (validationError) setError(validationError);
  }

  return (
    <div className="project-dialog-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="project-dialog" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title">
        <header>
          <div><small>{editing ? "项目设置" : "工作项目"}</small><h2 id="project-dialog-title">{editing ? "编辑项目" : "创建项目"}</h2></div>
          <button type="button" aria-label="关闭项目窗口" onClick={onClose}>×</button>
        </header>
        <form onSubmit={submit}>
          <label className="project-name-field">
            <span>项目名称</span>
            <span className="project-name-input"><UiIcon name="folder" /><input value={title} maxLength={32} onChange={(event) => { setTitle(event.target.value); setError(""); }} placeholder="例如：年度经营计划" autoComplete="off" /></span>
          </label>
          <label className="project-description-field">
            <span>项目说明 <small>可选</small></span>
            <textarea value={description} maxLength={120} rows={3} onChange={(event) => setDescription(event.target.value)} placeholder="说明该项目持续关注的经营主题或范围" />
            <small>创建后，可直接从项目中开始一条新会话。</small>
          </label>
          {error && <p className="project-dialog-error" role="alert">{error}</p>}
          <footer><button type="button" className="secondary-button" onClick={onClose}>取消</button><button type="submit" className="primary-button" disabled={!title.trim()}>{editing ? "保存修改" : "创建项目"}</button></footer>
        </form>
      </section>
    </div>
  );
}

export function StatusBadge({ tone, label }: { tone: Tone; label: string }) {
  return <span className={`status-badge ${tone}`}>{label}</span>;
}

export function ConfirmDialog({ state, onCancel, onConfirm }: { state: ConfirmState; onCancel: () => void; onConfirm: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    window.requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus());
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLButtonElement>("button:not([disabled])"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onCancel]);

  return <div className="overlay dialog-overlay" role="presentation"><section ref={dialogRef} className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><span className={`confirm-mark ${state.tone === "danger" ? "danger" : ""}`} aria-hidden="true">!</span><h2 id="confirm-title">{state.title}</h2><p>{state.description}</p><div><button type="button" className="secondary-button" onClick={onCancel}>取消</button><button type="button" className={state.tone === "danger" ? "danger-button" : "primary-button"} onClick={onConfirm}>{state.confirmLabel}</button></div></section></div>;
}

export function EmptyState({ title, description, action, onAction }: { title: string; description: string; action?: string; onAction?: () => void }) {
  return <section className="empty-state"><span aria-hidden="true">∅</span><h2>{title}</h2><p>{description}</p>{action && onAction && <button type="button" className="secondary-button" onClick={onAction}>{action}</button>}</section>;
}

export function Toast({ message }: { message: string }) {
  return <div className="toast" role="status" aria-live="polite"><span className="status-dot positive" aria-hidden="true" />{message}</div>;
}
