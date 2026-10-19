"use client";

import { createContext, useContext } from "react";
import { ApiError } from "@/lib/api";
import { DEMO_DISABLED_MESSAGE } from "@/lib/demo-message";

/** True on the hosted public demo, where the proxy refuses everything that writes or reads private data. */
export const DemoContext = createContext(false);

export const useDemo = () => useContext(DemoContext);

/**
 * Throw the same error the proxy would answer with, without making the request (a refused request
 * still shows up as a red 403 in the browser console).
 */
export function demoDisabled(): never {
  throw new ApiError(403, "disabled_in_demo", DEMO_DISABLED_MESSAGE);
}
