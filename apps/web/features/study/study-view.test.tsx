import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { DemoContext } from "@/lib/demo";
import { addLocalCard } from "@/lib/local-cards";
import { StudyView } from "./study-view";

// The public-demo mode keeps the deck in localStorage, so these run without an API.
const renderStudy = () => render(
  <DemoContext.Provider value={true}>
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><StudyView /></QueryClientProvider>
  </DemoContext.Provider>,
);

beforeEach(() => localStorage.clear());

describe("StudyView", () => {
  it("shows one friendly empty state, without zero tiles or an empty deck", async () => {
    renderStudy();
    expect(await screen.findByRole("heading", { name: "No flashcards yet" })).toBeInTheDocument();
    expect(screen.queryByText("Due now")).toBeNull();
    expect(screen.queryByRole("region", { name: "Deck" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Generate cards/ })).toBeNull(); // off in the demo
  });

  it("explains a missing answer instead of doing nothing, then returns focus to Front after adding", async () => {
    renderStudy();
    await screen.findByRole("heading", { name: "No flashcards yet" });
    fireEvent.change(screen.getByLabelText("Front (question)"), { target: { value: "What is LIFO?" } });
    fireEvent.click(screen.getByRole("button", { name: "Add card" }));
    expect(screen.getByText("Write the answer for the back of the card.")).toBeInTheDocument();
    expect(screen.getByLabelText("Back (answer)")).toHaveFocus();
    expect(screen.getByLabelText("Back (answer)")).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(screen.getByLabelText("Back (answer)"), { target: { value: "Last in, first out" } });
    fireEvent.click(screen.getByRole("button", { name: "Add card" }));
    await waitFor(() => expect(screen.getByLabelText("Front (question)")).toHaveFocus());
    expect(await screen.findByRole("region", { name: "Deck" })).toHaveTextContent("What is LIFO?");
  });

  it("reviews by keyboard: Space reveals, focus lands on the grades, a number grades and focus moves on", async () => {
    addLocalCard("First question", "First answer");
    addLocalCard("Second question", "Second answer");
    renderStudy();
    const question = await screen.findByRole("heading", { name: "First question" });
    expect(screen.getByText("Card 1 of 2")).toBeInTheDocument();
    fireEvent.keyDown(question, { key: " " });
    expect(screen.getByTestId("card-back")).toHaveTextContent("First answer");
    await waitFor(() => expect(screen.getByRole("button", { name: /^Again/ })).toHaveFocus());
    expect(screen.getByRole("button", { name: /^Good/ })).toHaveTextContent("1 day");
    fireEvent.keyDown(screen.getByRole("button", { name: /^Again/ }), { key: "3" });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Second question" })).toHaveFocus());
    expect(screen.getByText("Card 2 of 2")).toBeInTheDocument();
    expect(screen.getByText(/Saved\. Next review tomorrow/)).toBeInTheDocument();
  });

  it("asks before deleting a card and moves focus to the next one", async () => {
    addLocalCard("Alpha", "a");
    addLocalCard("Beta", "b");
    renderStudy();
    const deck = await screen.findByRole("region", { name: "Deck" });
    fireEvent.click(within(deck).getByRole("button", { name: "Delete card: Alpha" }));
    expect(within(deck).getByText("Alpha")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Confirm delete" })).toHaveFocus());
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Delete card: Beta" })).toHaveFocus());
    expect(screen.getByText("Deleted card “Alpha”.")).toBeInTheDocument();
  });

  it("does not let a long word widen the page", async () => {
    addLocalCard("x".repeat(300), "y");
    renderStudy();
    const deck = await screen.findByRole("region", { name: "Deck" });
    expect(within(deck).getByText("x".repeat(300)).className).toMatch(/overflow-wrap:anywhere/);
  });
});
