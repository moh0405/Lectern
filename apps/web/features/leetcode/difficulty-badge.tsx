import { Badge } from "@/components/ui/feedback";
import { cn } from "@/lib/utils";

export function DifficultyBadge({ difficulty }: { difficulty: string }) {
  return (
    <Badge
      className={cn(
        "font-medium",
        difficulty === "Easy" && "border-good/40 text-good",
        difficulty === "Medium" && "border-warn/40 text-warn",
        difficulty === "Hard" && "border-bad/40 text-bad",
      )}
    >
      {difficulty || "Unrated"}
    </Badge>
  );
}
