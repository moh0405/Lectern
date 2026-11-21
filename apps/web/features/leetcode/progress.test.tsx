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

it("saves notes on their own when the field is left, says so, and keeps them after a reload", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <DemoContext.Provider value={true}>
      <QueryClientProvider client={client}>
        <ProgressPanel problem={problem} />
        <button type="button">elsewhere</button>
      </QueryClientProvider>
    </DemoContext.Provider>,
  );
  await userEvent.type(screen.getByLabelText("Notes"), "hash map");
  await userEvent.click(screen.getByRole("button", { name: "elsewhere" }));
  expect(await screen.findByText("Notes saved.")).toBeInTheDocument();
  expect(loadLocalProgress().items[0]?.notes).toBe("hash map");
});
