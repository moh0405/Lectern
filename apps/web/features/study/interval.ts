/** "in 6 days", "in about 3 months": how far away a card's next review is. */
export function describeInterval(days: number): string {
  if (days <= 1) return "tomorrow";
  if (days < 30) return `in ${days} days`;
  if (days < 365) {
    const months = Math.round(days / 30);
    return `in about ${months} ${months === 1 ? "month" : "months"}`;
  }
  const years = Math.round((days / 365) * 10) / 10;
  return `in about ${years} ${years === 1 ? "year" : "years"}`;
}

/** "1 day", "6 days", "about 3 months": a short form for the grade buttons. */
export function shortInterval(days: number): string {
  if (days <= 1) return "1 day";
  return describeInterval(days).replace(/^in /, "");
}

/** The four review buttons, the SM-2 grade each one sends, and the key that presses them. */
export const GRADES = [
  { label: "Again", grade: 1, key: "1", hint: "I forgot it" },
  { label: "Hard", grade: 3, key: "2", hint: "I recalled it with effort" },
  { label: "Good", grade: 4, key: "3", hint: "I recalled it" },
  { label: "Easy", grade: 5, key: "4", hint: "No effort at all" },
] as const;

/**
 * Days until the next review if the card is graded `grade` now: the same SM-2 rules as backend/srs.py
 * (a lapse comes back tomorrow; then 1 day, 6 days, then the last interval times the ease factor).
 */
export function nextIntervalDays(card: { interval_days: number; repetitions: number; ef: number }, grade: number): number {
  if (grade < 3) return 1;
  if (card.repetitions === 0) return 1;
  if (card.repetitions === 1) return 6;
  return Math.max(1, Math.round(card.interval_days * card.ef));
}
