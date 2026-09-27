import type { HTMLAttributes } from "react";
import styles from "./Badge.module.css";

type Tone = "neutral" | "accent" | "success" | "danger";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: Tone;
};

export function Badge({ tone = "neutral", className, ...rest }: BadgeProps) {
  return (
    <span
      className={[styles.badge, styles[tone], className].filter(Boolean).join(" ")}
      {...rest}
    />
  );
}
