"""Hints are graduated scaffolding: the prompt asks for nudges, and a deterministic guard drops hints that
restate the hidden answer key the model writes in the same call (live-eval defect 6)."""

import json

import pytest

from backend.advanced_ai import guard_hints, hint_leaks_answer

DIJKSTRA_Q = "How does Dijkstra's algorithm work?"
DIJKSTRA_KEY = ("It repeatedly removes the unvisited vertex with the smallest tentative distance from a priority queue "
                "and relaxes its outgoing edges, updating a neighbour's distance whenever the path through the current "
                "vertex is shorter, until all reachable vertices are processed.")
HEAP_Q = "Why is inserting into a binary heap O(log n)?"
HEAP_KEY = ("The new element is placed at the bottom and swapped upward with its parent at most once per level, "
            "and a complete binary tree has height logarithmic in n, so the maximum number of swaps is the height.")

# The hints production showed (they give the answer away).
LEAKY = [
    (DIJKSTRA_Q, DIJKSTRA_KEY, "The algorithm always picks the vertex with the smallest tentative distance from the priority queue."),
    (DIJKSTRA_Q, DIJKSTRA_KEY, "It checks if the path through the current vertex is shorter than the previously recorded distance."),
    (DIJKSTRA_Q, DIJKSTRA_KEY, "It iteratively updates these distances until all reachable vertices have been processed."),
    (HEAP_Q, HEAP_KEY, "The maximum number of swaps required is equal to the height of the tree, which is logarithmic."),
    (HEAP_Q, "", "The answer is that each swap moves up one level."),
    (HEAP_Q, "", "This is because the tree is complete."),
]

# Hints the live eval judged good, and nudges of the shape the new prompt asks for.
GOOD = [
    (HEAP_Q, HEAP_KEY, "Consider the 'heap property' and what it requires of a parent and its children."),
    (HEAP_Q, HEAP_KEY, "Think about the 'bubble-up' and 'sift-down' operations described in heaps.pdf (page 2)."),
    (HEAP_Q, HEAP_KEY, "After you add the new element, how far could it possibly have to move?"),
    (HEAP_Q, HEAP_KEY, "How many levels does a complete binary tree with n nodes have?"),
    (DIJKSTRA_Q, DIJKSTRA_KEY, "Look at how graphs.pdf (page 7) keeps track of the best distance found so far to each vertex."),
    (DIJKSTRA_Q, DIJKSTRA_KEY, "Which vertex would you trust to have its final distance settled first, and why?"),
    (DIJKSTRA_Q, DIJKSTRA_KEY, "When you find a new route to a neighbour, what should you compare before changing anything?"),
]


@pytest.mark.parametrize("question, key, hint", LEAKY)
def test_guard_flags_hints_that_state_the_answer(question, key, hint):
    assert hint_leaks_answer(hint, key, question)


@pytest.mark.parametrize("question, key, hint", GOOD)
def test_guard_keeps_hints_that_nudge(question, key, hint):
    assert not hint_leaks_answer(hint, key, question)


def test_guard_without_answer_key_only_uses_patterns():
    assert not hint_leaks_answer("The heap is a tree.", "", HEAP_Q)
    kept, dropped = guard_hints(["Look at page 2.", "So the answer is log n."], "", HEAP_Q)
    assert kept == ["Look at page 2."] and dropped == 1


def test_prompt_asks_for_graduated_grounded_nudges(indexed, fake_gemini):
    passages = [{"text": "Insert places the key at the bottom and sifts it up.", "doc": "heaps.pdf", "page": 2}]
    r = indexed.post("/api/v1/socratic", json={"question": HEAP_Q, "context": passages, "depth": 2})
    assert r.status_code == 200
    prompt = fake_gemini.calls[-1]
    for phrase in ("answer_key", "Hint 1 points at the relevant concept", "middle hints ask a guiding question",
                   "student must still state the conclusion", "never as a declarative statement",
                   "Never write \"The answer is\"", "Stay grounded in the PASSAGES", "DEPTH: 2"):
        assert phrase in prompt
    assert "- [heaps.pdf (page 2)] Insert places the key" in prompt  # labelled so hints can cite the page


def test_prompt_says_when_there_are_no_passages(indexed, fake_gemini):
    indexed.post("/api/v1/socratic", json={"question": HEAP_Q, "k": 0})
    assert "(none: no study material matched" in fake_gemini.calls[-1]


def test_route_drops_leaky_hints_and_never_returns_the_answer_key(indexed, fake_gemini):
    hints = [
        "Look at how graphs.pdf (page 7) keeps track of the best distance found so far to each vertex.",
        "The algorithm always picks the vertex with the smallest tentative distance from the priority queue.",
        "When you find a new route to a neighbour, what should you compare before changing anything?",
    ]
    fake_gemini.handler = lambda p, j: json.dumps({"answer_key": DIJKSTRA_KEY, "questions": ["Where do you start?"],
                                                   "hints": hints})
    r = indexed.post("/api/v1/socratic", json={"question": DIJKSTRA_Q})
    body = r.json()
    assert r.status_code == 200
    assert body["hints"] == [hints[0], hints[2]]
    assert body["questions"] == ["Where do you start?"]
    assert "answer_key" not in body and DIJKSTRA_KEY not in r.text


def test_route_falls_back_when_every_hint_leaks(indexed, fake_gemini):
    fake_gemini.handler = lambda p, j: json.dumps({
        "answer_key": HEAP_KEY, "questions": [],
        "hints": ["The maximum number of swaps required is equal to the height of the tree, which is logarithmic."],
    })
    body = indexed.post("/api/v1/socratic", json={"question": HEAP_Q}).json()
    assert body["hints"] and all("swaps" not in h for h in body["hints"])
