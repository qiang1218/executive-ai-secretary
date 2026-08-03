"use client";

import { appMode } from "./production/runtime.mjs";
import { DemoProductPrototype } from "./demo/prototype";
import { ProductionApplication } from "./production/app";

export default function AppDispatcher() {
  return appMode === "production" ? <ProductionApplication /> : <DemoProductPrototype />;
}
