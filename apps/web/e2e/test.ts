import { test as base, expect } from "@playwright/test";
import { API } from "./helpers";

/**
 * `test` with one extra automatic step: the API keeps Ask history on the server, and a fresh browser restores it,
 * so every test starts from an empty server history (otherwise tests would see each other's questions).
 */
export const test = base.extend<{ cleanServerHistory: void }>({
  cleanServerHistory: [
    async ({ request }, use) => {
      await request.delete(`${API}/api/v1/history`);
      await use();
    },
    { auto: true },
  ],
});

export { expect };
