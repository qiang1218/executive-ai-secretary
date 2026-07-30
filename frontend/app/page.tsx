"use client";

import { appMode } from "./production/runtime.mjs";
import { DemoProductPrototype } from "./demo/prototype";
import { ProductionApplication } from "./production/app";

/**
 * Thin mode dispatcher. The single Next.js / vinext route entry is selected
 * at render time by {@link appMode}, so demo and production code stay in
 * physically separate files and the build pipeline never rewrites source.
 *
 * - dev (default): renders the interactive prototype with seeded fixtures.
 * - `NEXT_PUBLIC_APP_MODE=production npm run dev`: renders the production
 *   application against the real backend API.
 * - Docker / CI: `NEXT_PUBLIC_APP_MODE=production` is hard-coded in
 *   `Dockerfile.web`, so production bundles never carry demo fixtures.
 */
export default function RootPage() {
  return appMode === "production" ? <ProductionApplication /> : <DemoProductPrototype />;
}
