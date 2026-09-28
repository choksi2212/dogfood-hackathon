"use client";

import { useEffect, useState } from "react";

type Variant = "datetime" | "date" | "short";

type Props = {
  /** ISO 8601 string from the API. Null/undefined renders the fallback. */
  iso: string | null | undefined;
  /** Rendered when iso is empty or fails to parse. */
  fallback?: string;
  /**
   * - "datetime" → toLocaleString (e.g. "9/28/2026, 12:49:08 PM")
   * - "date"     → toLocaleDateString with month/day/year (en-US)
   * - "short"    → toLocaleDateString month: short (e.g. "Sep 28, 2026")
   */
  variant?: Variant;
  className?: string;
};

/**
 * Render a date that depends on the user's locale and timezone without
 * triggering a React hydration mismatch.
 *
 * Server renders `iso` (deterministic, no locale dependency). The first
 * client render also paints `iso`, so SSR HTML and the hydration
 * snapshot agree. After mount we swap in the locale-formatted string —
 * which is the entire reason this component exists, since plain
 * `new Date(iso).toLocaleString()` produces different output on Node
 * (UTC, en-US) vs the user's browser (local TZ, local locale).
 *
 * Same shape Mihir used for web/hooks/use-mobile.ts in 23e4b4c:
 * `useState(undefined)` initial value + `useEffect` post-mount. The
 * `<span suppressHydrationWarning>` is belt-and-braces in case a future
 * caller passes a derived value that drifts between server and client
 * even with the same input — the warning node opts that subtree out of
 * hydration-checking without disabling it for the rest of the tree.
 */
export function ClientDate({ iso, fallback = "—", variant = "datetime", className }: Props) {
  const [formatted, setFormatted] = useState<string | null>(null);

  useEffect(() => {
    if (!iso) return;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return;
    setFormatted(
      variant === "date"
        ? d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })
        : variant === "short"
          ? d.toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })
          : d.toLocaleString(),
    );
  }, [iso, variant]);

  if (!iso) return <span className={className}>{fallback}</span>;
  return (
    <span className={className} suppressHydrationWarning>
      {formatted ?? iso}
    </span>
  );
}
