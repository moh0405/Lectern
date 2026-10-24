/**
 * Flashcards for the public demo, kept in the visitor's browser (the shared server database stays off).
 * Same shapes as the API's `CardList`, and the same SM-2 rules as backend/srs.py, so the page behaves alike.
 */

export interface LocalCard {
  id: number;
  front: string;
  back: string;
  source: string | null;
  created_at: number;
  due_at: number;
  interval_days: number;
  ef: number;
  repetitions: number;
  lapses: number;
  reviews: number;
  last_reviewed: number | null;
}

export interface LocalCardList {
  cards: LocalCard[];
  stats: { total: number; due: number; new_cards: number; mature: number; reviews: number };
}

const KEY = "ai-study-mentor:cards:v1";
const DAY = 86400;
const MIN_EF = 1.3;
const MAX_CARDS = 500;

function isCard(v: unknown): v is LocalCard {
  const c = v as LocalCard;
  return !!c && typeof c.id === "number" && typeof c.front === "string" && typeof c.back === "string" && typeof c.due_at === "number" && typeof c.ef === "number";
}

function read(): LocalCard[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter(isCard) : [];
  } catch {
    return [];
  }
}

function write(cards: LocalCard[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(cards));
  } catch {
    // blocked or full: the deck lasts until reload only
  }
}

const now = () => Date.now() / 1000;

export function listLocalCards({ dueOnly = false, at = now() }: { dueOnly?: boolean; at?: number } = {}): LocalCardList {
  const all = read();
  const cards = (dueOnly ? all.filter((c) => c.due_at <= at) : all).sort((a, b) => a.due_at - b.due_at || a.id - b.id);
  return {
    cards,
    stats: {
      total: all.length,
      due: all.filter((c) => c.due_at <= at).length,
      new_cards: all.filter((c) => c.reviews === 0).length,
      mature: all.filter((c) => c.interval_days >= 21).length,
      reviews: all.reduce((n, c) => n + c.reviews, 0),
    },
  };
}

export function addLocalCard(front: string, back: string, at = now()): LocalCard {
  const all = read();
  if (all.length >= MAX_CARDS) throw new Error(`The demo deck holds up to ${MAX_CARDS} cards.`);
  const card: LocalCard = {
    id: all.reduce((m, c) => Math.max(m, c.id), 0) + 1,
    front: front.trim(),
    back: back.trim(),
    source: null,
    created_at: at,
    due_at: at,
    interval_days: 0,
    ef: 2.5,
    repetitions: 0,
    lapses: 0,
    reviews: 0,
    last_reviewed: null,
  };
  write([...all, card]);
  return card;
}

export function deleteLocalCard(id: number): void {
  write(read().filter((c) => c.id !== id));
}

/** SM-2, as in backend/srs.py. */
export function reviewLocalCard(id: number, grade: number, at = now()): LocalCard {
  const all = read();
  const card = all.find((c) => c.id === id);
  if (!card) throw new Error("Card not found");
  const ef = Math.max(MIN_EF, card.ef + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02));
  let { repetitions, interval_days, lapses } = card;
  if (grade < 3) {
    repetitions = 0;
    interval_days = 1;
    lapses += 1;
  } else {
    interval_days = repetitions === 0 ? 1 : repetitions === 1 ? 6 : Math.max(1, Math.round(card.interval_days * card.ef));
    repetitions += 1;
  }
  const next = { ...card, ef, repetitions, interval_days, lapses, reviews: card.reviews + 1, last_reviewed: at, due_at: at + interval_days * DAY };
  write(all.map((c) => (c.id === id ? next : c)));
  return next;
}
