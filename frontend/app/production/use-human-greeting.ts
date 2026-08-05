import { useEffect, useRef, useState } from "react";
import type { AuthMe } from "./types";
import type { UiLanguage } from "./workspace-types";

type GreetingContext = "time" | "return" | "idle";
type GreetingState = { context: GreetingContext; seed: string; observedAt: number };
type PresenceRecord = { dateKey: string; lastSeenAt: number; returnCount: number };

function zonedClock(timezone: string, now: Date = new Date()) {
  let hour = now.getHours();
  let dateKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "numeric",
      hour12: false,
      timeZone: timezone || "Asia/Shanghai",
    }).formatToParts(now);
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    if (values.hour) hour = Number(values.hour) % 24;
    if (values.year && values.month && values.day) dateKey = `${values.year}-${values.month}-${values.day}`;
  } catch {
    // Browser time is a safe display-only fallback.
  }
  return { hour, dateKey };
}

function stableGreetingIndex(seed: string, size: number) {
  let hash = 0;
  for (const character of seed) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  return Math.abs(hash) % Math.max(size, 1);
}

function timeGreeting(hour: number, language: UiLanguage, salutation: string) {
  if (language === "en") {
    if (hour < 5 || hour >= 23) return `It is late, take care, ${salutation}`;
    if (hour < 12) return `Good morning, ${salutation}`;
    if (hour < 18) return `Good afternoon, ${salutation}`;
    return `Good evening, ${salutation}`;
  }
  if (hour < 5 || hour >= 23) return language === "zh-TW" ? `夜深了，${salutation}` : `夜深了，${salutation}`;
  if (hour < 10) return language === "zh-TW" ? `早上好，${salutation}` : `早上好，${salutation}`;
  if (hour < 13) return language === "zh-TW" ? `中午好，${salutation}` : `中午好，${salutation}`;
  if (hour < 18) return language === "zh-TW" ? `下午好，${salutation}` : `下午好，${salutation}`;
  return language === "zh-TW" ? `晚上好，${salutation}` : `晚上好，${salutation}`;
}

function contextualGreeting(state: GreetingState, timezone: string, language: UiLanguage, salutation: string) {
  const { hour } = zonedClock(timezone, new Date(state.observedAt));
  if (state.context === "time") return timeGreeting(hour, language, salutation);
  if (language === "en") {
    if (hour < 5 || hour >= 23) return `It is late, remember to rest, ${salutation}`;
    const values = state.context === "idle"
      ? [`You have worked hard, ${salutation}.`, `Take a moment to breathe, ${salutation}.`]
      : [`Welcome back, ${salutation}.`, `Good to see you again, ${salutation}.`, `I missed you, ${salutation}.`];
    return values[stableGreetingIndex(state.seed, values.length)];
  }
  const traditional = language === "zh-TW";
  if (hour < 5 || hour >= 23) return traditional ? `夜深了，注意休息，${salutation}` : `夜深了，注意休息，${salutation}`;
  const values = state.context === "idle"
      ? traditional
      ? [`工作辛苦了，${salutation}。`, `放鬆一下吧，${salutation}。`]
      : [`工作辛苦了，${salutation}。`, `放松一下吧，${salutation}。`]
    : traditional
      ? [`歡迎回來，${salutation}！`, `${salutation} 回來了！`, `${salutation}，我很想你！`]
      : [`欢迎回来，${salutation}！`, `${salutation} 回来了！`, `${salutation}，我很想你！`];
  return values[stableGreetingIndex(state.seed, values.length)];
}

function readPresenceRecord(key: string): PresenceRecord | null {
  try {
    const value = JSON.parse(window.localStorage.getItem(key) || "null") as Partial<PresenceRecord> | null;
    if (!value || typeof value.dateKey !== "string" || typeof value.lastSeenAt !== "number" || typeof value.returnCount !== "number") return null;
    return { dateKey: value.dateKey, lastSeenAt: value.lastSeenAt, returnCount: value.returnCount };
  } catch {
    return null;
  }
}

export function useHumanGreeting(me: AuthMe, language: UiLanguage, salutation: string) {
  const timezone = me.user.timezone || "Asia/Shanghai";
  const [state, setState] = useState<GreetingState>(() => {
    const now = Date.now();
    if (typeof window === "undefined") return { context: "time", seed: "initial", observedAt: now };
    const { dateKey } = zonedClock(timezone, new Date(now));
    const previous = readPresenceRecord(`executive-workbench-presence:${me.user.id}`);
    const returningToday = previous?.dateKey === dateKey;
    const returnCount = returningToday ? previous.returnCount + 1 : 0;
    return {
      context: returningToday ? "return" : "time",
      seed: `${me.user.id}:${dateKey}:${returnCount}`,
      observedAt: now,
    };
  });
  const stateRef = useRef(state);
  const lastActivityAt = useRef<number | null>(null);
  const hiddenAt = useRef<number | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const userKey = me.user.id;
    const presenceKey = `executive-workbench-presence:${userKey}`;
    const now = Date.now();
    const { dateKey } = zonedClock(timezone, new Date(now));
    const previous = readPresenceRecord(presenceKey);
    let returnCount = previous?.dateKey === dateKey ? previous.returnCount : 0;
    if (previous?.dateKey === dateKey) returnCount += 1;
    lastActivityAt.current = now;
    window.localStorage.setItem(presenceKey, JSON.stringify({ dateKey, lastSeenAt: now, returnCount } satisfies PresenceRecord));

    const rememberPresence = () => {
      const timestamp = Date.now();
      const currentDateKey = zonedClock(timezone, new Date(timestamp)).dateKey;
      const current = readPresenceRecord(presenceKey);
      window.localStorage.setItem(presenceKey, JSON.stringify({
        dateKey: currentDateKey,
        lastSeenAt: timestamp,
        returnCount: current?.dateKey === currentDateKey ? current.returnCount : 0,
      } satisfies PresenceRecord));
    };
    const showContext = (context: GreetingContext, timestamp: number) => {
      const nextDateKey = zonedClock(timezone, new Date(timestamp)).dateKey;
      const nextState: GreetingState = { context, seed: `${userKey}:${nextDateKey}:${context}:${Math.floor(timestamp / 300_000)}`, observedAt: timestamp };
      stateRef.current = nextState;
      setState(nextState);
    };
    const onVisibilityChange = () => {
      const timestamp = Date.now();
      if (document.visibilityState === "hidden") {
        hiddenAt.current = timestamp;
        rememberPresence();
        return;
      }
      const elapsed = hiddenAt.current ? timestamp - hiddenAt.current : 0;
      hiddenAt.current = null;
      if (elapsed >= 45 * 60_000) showContext("idle", timestamp);
      else if (elapsed >= 5 * 60_000) showContext("return", timestamp);
      lastActivityAt.current = timestamp;
    };
    const onActivity = () => {
      const timestamp = Date.now();
      if (lastActivityAt.current !== null && timestamp - lastActivityAt.current >= 45 * 60_000) showContext("idle", timestamp);
      lastActivityAt.current = timestamp;
    };
    const timer = window.setInterval(() => {
      const timestamp = Date.now();
      const currentDateKey = zonedClock(timezone, new Date(timestamp)).dateKey;
      if (currentDateKey !== zonedClock(timezone, new Date(stateRef.current.observedAt)).dateKey) showContext("time", timestamp);
      else if (document.visibilityState === "visible" && lastActivityAt.current !== null && timestamp - lastActivityAt.current >= 45 * 60_000 && stateRef.current.context !== "idle") showContext("idle", timestamp);
      else setState((current) => ({ ...current, observedAt: timestamp }));
    }, 60_000);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pointerdown", onActivity);
    window.addEventListener("keydown", onActivity);
    window.addEventListener("pagehide", rememberPresence);
    return () => {
      rememberPresence();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pointerdown", onActivity);
      window.removeEventListener("keydown", onActivity);
      window.removeEventListener("pagehide", rememberPresence);
    };
  }, [me.user.id, timezone]);

  return contextualGreeting(state, timezone, language, salutation);
}
