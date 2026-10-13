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

/** The four review buttons and the SM-2 grade each one sends. */
export const GRADES = [
  { label: "Again", grade: 1, hint: "I forgot it" },
  { label: "Hard", grade: 3, hint: "I recalled it with effort" },
  { label: "Good", grade: 4, hint: "I recalled it" },
  { label: "Easy", grade: 5, hint: "No effort at all" },
] as const;
