"use client";

import { useEffect, useState } from "react";

export type ThemePreference = "system" | "light" | "dark";
export type UiLanguage = "zh-CN" | "zh-TW" | "en";

const THEME_STORAGE_KEY = "executive-workbench-theme";
const LANGUAGE_STORAGE_KEY = "executive-workbench-language";

/**
 * 管理主题偏好的状态 + DOM 副作用 + localStorage 持久化。
 * 替代各组件中重复的 useState + useEffect 主题逻辑。
 */
export function useThemePreference(initial: ThemePreference = "system") {
  const [theme, setTheme] = useState<ThemePreference>(() => {
    if (typeof window === "undefined") return initial;
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
    return saved === "light" || saved === "dark" || saved === "system" ? saved : initial;
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme === "system" ? "light dark" : theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  return [theme, setTheme] as const;
}

/**
 * 管理界面语言偏好的状态 + DOM lang 属性 + localStorage 持久化。
 */
export function useLanguagePreference(initial: UiLanguage = "zh-CN") {
  const [language, setLanguage] = useState<UiLanguage>(() => {
    if (typeof window === "undefined") return initial;
    const saved = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return saved === "zh-TW" || saved === "en" || saved === "zh-CN" ? saved : initial;
  });

  useEffect(() => {
    document.documentElement.lang = language;
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

  return [language, setLanguage] as const;
}

/**
 * 仅在挂载时从 localStorage 读取并应用主题（不支持运行时切换）。
 * 用于不需要主题状态的管理端等页面。
 */
export function useStoredTheme() {
  useEffect(() => {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
    const theme: ThemePreference =
      saved === "light" || saved === "dark" || saved === "system" ? saved : "system";
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme === "system" ? "light dark" : theme;
    if (!saved) window.localStorage.setItem(THEME_STORAGE_KEY, "system");
  }, []);
}
