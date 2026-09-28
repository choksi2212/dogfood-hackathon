"use client";
import { useHydrated } from "@/hooks/use-hydrated";
type Props = {
  iso: string | null | undefined;
  fallback?: string;
  variant?: "datetime" | "date" | "short";
  className?: string;
};
export function ClientDate({
  iso,
  fallback = "—",
  variant = "datetime",
  className,
}: Props) {
  const hydrated = useHydrated();
  const date = iso ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime()))
    return <span className={className}>{fallback}</span>;
  const formatted =
    variant === "datetime"
      ? date.toLocaleString()
      : date.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        });
  return (
    <time className={className} dateTime={iso ?? undefined}>
      {hydrated ? formatted : iso}
    </time>
  );
}
