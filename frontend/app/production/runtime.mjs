const VALID_APP_MODES = new Set(["demo", "production"]);

/**
 * Resolve the application's render mode from the public environment variable.
 *
 * The default is `production` so an unconfigured local checkout targets the
 * real backend instead of the seeded demo fixtures. Operators who want the
 * interactive prototype in development must opt in explicitly via
 * `NEXT_PUBLIC_APP_MODE=demo`. Unknown values fail closed during startup so
 * a misspelled environment variable can never silently expose demo fixtures.
 *
 * @param {string | undefined | null} value
 * @returns {"demo" | "production"}
 */
export function resolveAppMode(value) {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return "production";
  if (VALID_APP_MODES.has(normalized)) return normalized;
  throw new Error(
    `Invalid NEXT_PUBLIC_APP_MODE "${value}". Expected "demo" or "production".`,
  );
}

export const appMode = resolveAppMode(process.env.NEXT_PUBLIC_APP_MODE);

/** @returns {boolean} */
export function isProductionMode() {
  return appMode === "production";
}
