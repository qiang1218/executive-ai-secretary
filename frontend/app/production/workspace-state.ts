import type { ProductionBootstrap } from "./types";
import type {
  ProfilePreferences,
  ThemePreference,
  UiLanguage,
} from "./workspace-types";

export type WorkspaceStateInputs = {
  initialBootstrap: ProductionBootstrap;
};

export type WorkspaceDerivedState = {
  businessDataReady: boolean;
  dailyBriefScopeRequestKey: string;
  selectedScopeLabel: string;
  userInitials: string;
};

export function readStoredUnreadConversationIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem("executive-workbench-unread-conversations") || "[]",
    );
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function readStoredTheme(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const saved = window.localStorage.getItem("executive-workbench-theme");
  return saved === "light" || saved === "dark" || saved === "system" ? saved : "system";
}

export function resolveInitialLanguage(bootstrap: ProductionBootstrap): UiLanguage {
  if (typeof window === "undefined") return "zh-CN";
  const profileLocale = bootstrap.personalProfile?.locale;
  if (profileLocale === "zh-CN" || profileLocale === "zh-TW") return profileLocale;
  if (profileLocale === "en-US") return "en";
  return bootstrap.me.user.locale === "zh-TW" || bootstrap.me.user.locale === "en"
    ? bootstrap.me.user.locale
    : "zh-CN";
}

export function resolveInitialProfilePreferences(
  bootstrap: ProductionBootstrap,
): ProfilePreferences {
  return {
    salutation: bootstrap.personalProfile?.salutation || "董事长",
    amountUnit: bootstrap.personalProfile?.amount_unit || "wan",
    responseStyle: bootstrap.personalProfile?.response_style || "balanced",
  };
}

export function resolveInitialModelId(bootstrap: ProductionBootstrap): string {
  return (
    bootstrap.authorizedModels.find((model) => model.is_default)?.model_id
    ?? bootstrap.authorizedModels[0]?.model_id
    ?? ""
  );
}
