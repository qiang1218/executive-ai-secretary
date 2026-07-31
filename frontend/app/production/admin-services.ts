import { ApiClient, apiClient } from "./api-client";
import type {
  AdminAuditEvent,
  AdminAuditVerification,
  AdminOrganizationUnit,
  AdminRuntimeStatus,
  AdminUser,
  Page,
} from "./types";

function queryString(values: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value != null) query.set(key, String(value));
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export type AdminServices = ReturnType<typeof createAdminServices>;

export function createAdminServices(client: ApiClient = apiClient) {
  return {
    users: {
      async list(cursor?: string | null) {
        return client.request<Page<AdminUser>>(`/admin/users${queryString({ cursor })}`);
      },
      async create(payload: {
        email: string;
        display_name: string;
        preferred_name?: string | null;
        role: AdminUser["role"];
        temporary_password: string;
        organization_unit_ids: string[];
        enterprise_wide_scope: boolean;
      }) {
        return client.request<AdminUser>("/admin/users", { method: "POST", body: payload });
      },
      async update(userId: string, payload: {
        display_name?: string | null;
        preferred_name?: string | null;
        role?: AdminUser["role"] | null;
        is_active?: boolean | null;
        locale?: "zh-CN" | "zh-TW" | "en-US" | null;
        timezone?: string | null;
      }) {
        return client.request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`, {
          method: "PATCH",
          body: payload,
        });
      },
      async resetPassword(userId: string, temporaryPassword: string) {
        return client.request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}/reset-password`, {
          method: "POST",
          body: { temporary_password: temporaryPassword },
        });
      },
      async updateDataScopes(userId: string, payload: {
        enterprise_wide_scope: boolean;
        organization_unit_ids: string[];
      }) {
        return client.request<AdminOrganizationUnit[]>(
          `/admin/users/${encodeURIComponent(userId)}/data-scopes`,
          { method: "PUT", body: payload },
        );
      },
      async revokeSessions(userId: string) {
        await client.request<void>(`/admin/users/${encodeURIComponent(userId)}/sessions`, {
          method: "DELETE",
        });
      },
    },
    organizationUnits: {
      async list(cursor?: string | null) {
        return client.request<Page<AdminOrganizationUnit>>(
          `/admin/organization-units${queryString({ cursor })}`,
        );
      },
      async create(payload: {
        name: string;
        code: string;
        parent_id?: string | null;
        unit_type?: string;
        enabled_for_analysis?: boolean;
        data_connected?: boolean;
        sort_order?: number;
      }) {
        return client.request<AdminOrganizationUnit>("/admin/organization-units", {
          method: "POST",
          body: payload,
        });
      },
      async update(unitId: string, payload: {
        name?: string | null;
        parent_id?: string | null;
        enabled_for_analysis?: boolean | null;
        data_connected?: boolean | null;
        sort_order?: number | null;
        is_active?: boolean | null;
      }) {
        return client.request<AdminOrganizationUnit>(
          `/admin/organization-units/${encodeURIComponent(unitId)}`,
          { method: "PATCH", body: payload },
        );
      },
    },
    audit: {
      async list(cursor?: string | null, options: { limit?: number } = {}) {
        return client.request<Page<AdminAuditEvent>>(
          `/admin/audit-events${queryString({ cursor, limit: options.limit })}`,
        );
      },
      async verify() {
        return client.request<AdminAuditVerification>("/admin/audit-events/verify", {
          method: "POST",
        });
      },
    },
    runtime: {
      async get() {
        return client.request<AdminRuntimeStatus>("/admin/runtime");
      },
    },
  };
}

export const adminServices = createAdminServices();