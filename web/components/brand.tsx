import Link from "next/link";
import { PawPrint } from "lucide-react";
import { cn } from "@/lib/cn";

export function Brand({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  return (
    <Link
      href="/"
      aria-label="Dogfood home"
      className={cn(
        "inline-flex items-center gap-2.5 font-display text-xl font-semibold tracking-tight",
        className,
      )}
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-text-inverse">
        <PawPrint className="size-5" />
      </span>
      {!compact && (
        <span className="group-data-[collapsible=icon]:hidden">
          dogfood<span className="text-accent">.</span>
        </span>
      )}
    </Link>
  );
}
