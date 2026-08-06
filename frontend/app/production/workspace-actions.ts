import type {
  Conversation,
  ConversationMessage,
  Job,
  Project,
} from "./types";
import type { OrganizationScope } from "./types";
import type {
  ConversationProjectDialogState,
  ProjectDialogState,
  SidebarMenuState,
  ConfirmState,
} from "./workspace-types";

export type OpenSidebarMenuInput =
  | { kind: "conversation"; conversationId: string }
  | { kind: "project"; projectId: string };

export function computeSidebarMenuTop(
  event: React.MouseEvent<HTMLButtonElement>,
): number {
  return Math.min(
    event.currentTarget.getBoundingClientRect().top,
    window.innerHeight - 310,
  );
}

export function buildSidebarMenuState(
  event: React.MouseEvent<HTMLButtonElement>,
  input: OpenSidebarMenuInput,
): SidebarMenuState {
  return {
    ...input,
    top: computeSidebarMenuTop(event),
  } as SidebarMenuState;
}

export function findJobForMessage(
  jobs: Job[],
  messageId: string,
): Job | undefined {
  return jobs.find(
    (job) => String(job.payload_json.assistant_message_id || "") === messageId,
  );
}

export function buildArchiveConversationConfirm(
  conversation: Conversation,
  action: () => Promise<void>,
): ConfirmState {
  return {
    title: "归档这条会话？",
    description: `“${conversation.title}”将从工作台列表移除，数据仍保留在受控存储中。`,
    confirmLabel: "归档会话",
    tone: "danger",
    action,
  };
}

export function buildArchiveProjectTasksConfirm(
  project: Project,
  action: () => Promise<void>,
): ConfirmState {
  return {
    title: "归档项目内的全部会话？",
    description: `“${project.name}”项目仍会保留，但其中的现有会话将全部归档。`,
    confirmLabel: "归档全部会话",
    tone: "danger",
    action,
  };
}

export function buildRemoveProjectConfirm(
  project: Project,
  action: () => Promise<void>,
): ConfirmState {
  return {
    title: "移除这个项目？",
    description: `“${project.name}”将从项目列表移除。项目内会话不会被删除，仍可在历史会话中找到。`,
    confirmLabel: "移除项目",
    tone: "danger",
    action,
  };
}

export function buildDeleteMemoryConfirm(
  memory: { id: string; title: string },
  action: () => Promise<void>,
): ConfirmState {
  return {
    title: "删除这条长期记忆？",
    description: `“${memory.title}”将不再用于后续会话。`,
    confirmLabel: "删除记忆",
    tone: "danger",
    action,
  };
}

export function buildScopeChangeMessage(
  message: ConversationMessage,
  organizationScope: OrganizationScope,
): ConversationMessage {
  return {
    ...message,
    content: `已切换数据范围：${organizationScope.mode === "all_authorized" ? "全部授权事业部" : `${organizationScope.organization_unit_ids.length} 个事业部`}`,
    content_json: {
      ...message.content_json,
      event: "organization_scope_changed",
    },
  };
}

export function buildProjectDialogStateForEdit(projectId: string): ProjectDialogState {
  return { mode: "edit", projectId };
}

export function buildProjectDialogStateForCreate(): ProjectDialogState {
  return { mode: "create" };
}

export function buildConversationProjectDialogState(
  conversationId: string,
): ConversationProjectDialogState {
  return { conversationId };
}
