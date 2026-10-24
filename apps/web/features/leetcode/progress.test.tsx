import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";
import { DemoContext } from "@/lib/demo";
import { loadLocalProgress } from "@/lib/local-progress";
import { ProgressPanel } from "./progress";

const problem = { pid: "1", title: "Two Sum", difficulty: "Easy", topics: ["Array"] };

beforeEach(() => localStorage.clear());

it("in the public demo, marks are kept in this browser and never sent to the server", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <DemoContext.Provider value={true}>
      <QueryClientProvider client={client}>
        <ProgressPanel problem={problem} />
      </QueryClientProvider>
    </DemoContext.Provider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Solved" }));
  await waitFor(() => expect(loadLocalProgress().summary.solved).toBe(1));
  expect(screen.getByRole("button", { name: "Solved" })).toHaveAttribute("aria-pressed", "true");
});
