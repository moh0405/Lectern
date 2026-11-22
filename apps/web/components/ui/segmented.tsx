"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import styles from "./segmented.module.css";

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  /** Shown to screen readers after the label, and as a tooltip. */
  description?: string;
}

/**
 * A single choice as a segmented control: native radio buttons in a fieldset, so arrow keys move the choice, Tab
 * enters and leaves the group once, and screen readers announce "radio, 2 of 3". Each segment is the whole hit area
 * (the invisible input covers it), at least 44px tall on phones and touch screens.
 */
export function Segmented<T extends string>({ legend, legendVisible = false, name, options, value, onChange, className, fill = false }: {
  legend: string;
  legendVisible?: boolean;
  name: string;
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  /** Stretch the segments to the full width of the container. */
  fill?: boolean;
}) {
  return (
    <fieldset className={cn(styles.group, className)} data-fill={fill || undefined}>
      <legend className={legendVisible ? styles.legend : "sr-only"}>{legend}</legend>
      <div className={styles.track}>
        {options.map((o) => (
          <label key={o.value} className={styles.option} title={o.description}>
            <input
              type="radio"
              className={styles.input}
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              aria-describedby={o.description ? `${name}-${o.value}-desc` : undefined}
            />
            <span className={styles.text}>{o.label}</span>
          </label>
        ))}
      </div>
      {/* Outside the labels, so a description is read as the radio's description, not as part of its name. */}
      {options.map((o) => (o.description ? <span key={o.value} id={`${name}-${o.value}-desc`} className="sr-only">{o.description}</span> : null))}
    </fieldset>
  );
}
