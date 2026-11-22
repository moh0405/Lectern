import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

/*
 * Focus: the global :focus-visible outline uses accent-2, but `transition-colors` also animates
 * outline-color, which starts from currentColor (accent-fg, dark on the lavender fill), so the ring
 * faded in from nearly invisible. Transition only the fill, text and border colours, and state the
 * ring here so it is accent-2 with an offset in both themes from the first frame.
 */
const button = cva(
  "lectern-button inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-[color,background-color,border-color] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-accent-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-fg hover:bg-accent/85",
        secondary: "border border-border bg-surface-2 text-fg hover:border-accent/60",
        ghost: "text-muted hover:bg-surface-2 hover:text-fg",
        danger: "border border-bad/40 text-bad hover:bg-bad/10",
      },
      size: { sm: "min-h-10 px-3 pointer-coarse:min-h-11", md: "min-h-11 px-4", icon: "h-11 w-11" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends ComponentProps<"button">, VariantProps<typeof button> {}

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cn(button({ variant, size }), className)} {...props} />;
}
