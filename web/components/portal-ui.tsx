import Link from "next/link";
import { AlertCircle, Inbox, ArrowRight, type LucideIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export function PageHeading({
  eyebrow = "HACK HAMSTER / 2026",
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
      <div>
        <p className="eyebrow mb-3">{eyebrow}</p>
        <h1 className="font-display text-3xl leading-tight font-medium tracking-display sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl leading-relaxed text-text-secondary">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  href,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description: string;
  href?: string;
  action?: string;
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed bg-bg-elevated px-6 py-16 text-center">
      <span className="mb-5 flex size-16 items-center justify-center rounded-2xl bg-accent-dim text-accent">
        <Icon className="size-7" />
      </span>
      <h2 className="text-xl font-medium tracking-tight">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-text-secondary">
        {description}
      </p>
      {href && (
        <Link
          href={href}
          className={cn(buttonVariants({ variant: "outline" }), "mt-6")}
        >
          {action ?? "Continue"}
          <ArrowRight className="size-4" />
        </Link>
      )}
    </div>
  );
}
export function LoadError({
  title = "We couldn’t load this page",
  description = "Please try again. Your work is safe.",
  href,
}: {
  title?: string;
  description?: string;
  href?: string;
}) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="size-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="flex flex-wrap items-center justify-between gap-4">
        <span>{description}</span>
        {href && (
          <a
            href={href}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            Try again
          </a>
        )}
      </AlertDescription>
    </Alert>
  );
}
export function ProgressRing({
  value,
  total,
}: {
  value: number;
  total: number;
}) {
  const fraction = total ? Math.min(value / total, 1) : 0;
  return (
    <div
      className="relative size-28 shrink-0"
      role="img"
      aria-label={`${value} of ${total} reviewed`}
    >
      <svg
        viewBox="0 0 100 100"
        className="size-full -rotate-90"
        aria-hidden="true"
      >
        <circle
          cx="50"
          cy="50"
          r="43"
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="5"
        />
        <circle
          cx="50"
          cy="50"
          r="43"
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray="270.18"
          strokeDashoffset={270.18 * (1 - fraction)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-2xl tabular-nums">
          {value}
          <span className="text-sm text-text-muted">/{total}</span>
        </span>
        <span className="mt-1 text-xs text-text-secondary">reviewed</span>
      </div>
    </div>
  );
}
