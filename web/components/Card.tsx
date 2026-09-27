import type { HTMLAttributes } from "react";
import styles from "./Card.module.css";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  interactive?: boolean;
};

export function Card({ interactive = false, className, ...rest }: CardProps) {
  return (
    <div
      className={[styles.card, interactive && styles.interactive, className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    />
  );
}
