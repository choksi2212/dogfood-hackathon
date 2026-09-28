"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Equal,
  Keyboard,
  Loader2,
  RotateCcw,
  Scale,
  Trophy,
} from "lucide-react";
import { api } from "@/lib/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState, PageHeading } from "@/components/portal-ui";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import type { PairwiseWinner, Submission } from "@/lib/api/types";

function pairKey(left: Submission, right: Submission) {
  return [left.id, right.id].sort().join(":");
}

function pickPair(
  pool: Submission[],
  seenKeys: Set<string>,
): [Submission, Submission] | null {
  if (pool.length < 2) return null;
  function randomPair(): [Submission, Submission] {
    const left = Math.floor(Math.random() * pool.length);
    const right =
      (left + 1 + Math.floor(Math.random() * (pool.length - 1))) % pool.length;
    return [pool[left], pool[right]];
  }
  for (let attempt = 0; attempt < 30; attempt++) {
    const pair = randomPair();
    if (!seenKeys.has(pairKey(...pair))) return pair;
  }
  for (let left = 0; left < pool.length; left++) {
    for (let right = left + 1; right < pool.length; right++) {
      if (!seenKeys.has(pairKey(pool[left], pool[right])))
        return Math.random() < 0.5
          ? [pool[left], pool[right]]
          : [pool[right], pool[left]];
    }
  }
  return randomPair();
}

export function PairwiseCompare() {
  const reducedMotion = useReducedMotion();
  const [pool, setPool] = useState<Submission[] | null>(null);
  const [pair, setPair] = useState<[Submission, Submission] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [voteError, setVoteError] = useState(false);
  const [pending, setPending] = useState<PairwiseWinner | null>(null);
  const [count, setCount] = useState(0);
  const seenKeys = useRef(new Set<string>());
  const inFlight = useRef(false);
  const mounted = useRef(false);
  const loadVersion = useRef(0);

  const loadProjects = useCallback(async () => {
    const version = ++loadVersion.current;
    try {
      const projects = await api.allGallery();
      if (!mounted.current || version !== loadVersion.current) return;
      setPool(projects);
      setPair(pickPair(projects, seenKeys.current));
    } catch {
      if (mounted.current && version === loadVersion.current)
        setLoadError(true);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void Promise.resolve().then(loadProjects);
    return () => {
      mounted.current = false;
    };
  }, [loadProjects]);

  const choose = useCallback(
    async (winner: PairwiseWinner) => {
      if (!pair || !pool || inFlight.current) return;
      inFlight.current = true;
      setPending(winner);
      setVoteError(false);
      const [left, right] = pair;
      try {
        await api.pairwiseBallot({
          left_id: left.id,
          right_id: right.id,
          winner,
        });
        if (!mounted.current) return;
        seenKeys.current.add(pairKey(left, right));
        setCount((previous) => previous + 1);
        setPair(pickPair(pool, seenKeys.current));
      } catch {
        if (mounted.current) setVoteError(true);
      } finally {
        inFlight.current = false;
        if (mounted.current) setPending(null);
      }
    },
    [pair, pool],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (
        event.repeat ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.defaultPrevented
      )
        return;
      if (
        event.target instanceof Element &&
        event.target.closest(
          'input, textarea, select, button, a, [contenteditable="true"], [role="button"], [role="slider"], [role="menu"], [role="dialog"]',
        )
      )
        return;
      const winner =
        event.key === "ArrowLeft"
          ? "left"
          : event.key === "ArrowRight"
            ? "right"
            : event.key.toLowerCase() === "t"
              ? "tie"
              : null;
      if (winner) {
        event.preventDefault();
        void choose(winner);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [choose]);

  return (
    <div>
      <PageHeading
        eyebrow="JUDGING / COMPARISONS"
        title="Two ideas. Your call."
        description="Compare the projects as a whole. Choose the stronger entry, or call a tie when they’re evenly matched."
        action={
          <Link
            href="/pairwise/ranking"
            className={buttonVariants({ variant: "outline" })}
          >
            <Trophy className="size-4" />
            View ranking
          </Link>
        }
      />
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-bg-elevated px-5 py-4">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-secondary">
          <Keyboard className="size-4 text-text-muted" aria-hidden="true" />
          <span>
            <kbd className="mr-1 rounded border bg-bg px-1.5 py-1 font-mono">
              ←
            </kbd>{" "}
            left wins
          </span>
          <span>
            <kbd className="mr-1 rounded border bg-bg px-1.5 py-1 font-mono">
              →
            </kbd>{" "}
            right wins
          </span>
          <span>
            <kbd className="mr-1 rounded border bg-bg px-1.5 py-1 font-mono">
              T
            </kbd>{" "}
            tie
          </span>
        </div>
        <p
          className="flex items-center gap-2 text-xs text-text-secondary"
          aria-live="polite"
        >
          <CheckCircle2 className="size-3.5 text-success" />
          <span className="font-mono text-base tabular-nums text-text-primary">
            {count}
          </span>{" "}
          compared this session
        </p>
      </div>
      {loadError ? (
        <Alert variant="destructive">
          <Scale className="size-4" />
          <AlertTitle>We couldn’t load the projects</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-4">
            <span>Try again to start comparing submissions.</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setLoadError(false);
                setPool(null);
                void loadProjects();
              }}
            >
              <RotateCcw className="size-3.5" />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : pool === null ? (
        <PairwiseSkeleton />
      ) : pool.length < 2 ? (
        <EmptyState
          icon={Scale}
          title="A comparison needs two ideas"
          description="There aren’t enough submitted projects yet. Check back when more teams have shipped their work."
          href="/gallery"
          action="Explore the gallery"
        />
      ) : (
        pair && (
          <>
            {voteError && (
              <Alert variant="destructive" className="mb-5" role="alert">
                <Scale className="size-4" />
                <AlertTitle>Your comparison wasn’t saved</AlertTitle>
                <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                  <span>Choose again to retry. This pair is still here.</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setVoteError(false)}
                  >
                    Dismiss
                  </Button>
                </AlertDescription>
              </Alert>
            )}
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={`${pair[0].id}:${pair[1].id}:${count}`}
                initial={reducedMotion ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reducedMotion ? 0 : -6 }}
                transition={{ duration: reducedMotion ? 0 : 0.25 }}
                className="grid items-stretch gap-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:gap-5"
              >
                {(["left", "right"] as const).map((side, index) => (
                  <article
                    key={side}
                    className={cn(
                      "surface group relative flex flex-col overflow-hidden",
                      side === "right" && "md:col-start-3 md:row-start-1",
                      pending === side && "border-accent",
                    )}
                  >
                    <motion.button
                      type="button"
                      disabled={pending !== null}
                      aria-label={`Choose ${pair[index].name} as the ${side} winner`}
                      whileHover={
                        reducedMotion || pending ? undefined : { scale: 1.01 }
                      }
                      whileTap={
                        reducedMotion || pending ? undefined : { scale: 0.99 }
                      }
                      transition={{ duration: 0.2 }}
                      onClick={() => void choose(side)}
                      className="flex flex-1 flex-col p-6 text-left disabled:cursor-wait sm:p-8"
                    >
                      <div className="mb-8 flex w-full items-center justify-between gap-3">
                        <span className="eyebrow text-xs text-text-muted">
                          {side === "left" ? "PROJECT A" : "PROJECT B"}
                        </span>
                        <Badge
                          variant="outline"
                          className="h-auto max-w-full bg-accent-dim py-1 text-xs text-accent"
                        >
                          {pair[index].track_slug.replace(/-/g, " ")}
                        </Badge>
                      </div>
                      <div
                        className="project-art relative mb-7 flex h-36 w-full items-center justify-center overflow-hidden rounded-xl border"
                        aria-hidden="true"
                      >
                        <span className="relative z-10 font-mono text-5xl font-light tracking-tighter text-accent/60">
                          {pair[index].name
                            .split(/\s+/)
                            .map((word) => word[0])
                            .slice(0, 2)
                            .join("")
                            .toUpperCase()}
                        </span>
                        <div className="mesh-grid absolute inset-0 opacity-[.025]" />
                      </div>
                      <h2 className="text-2xl leading-tight font-medium tracking-display sm:text-3xl">
                        {pair[index].name}
                      </h2>
                      <p className="mt-4 min-h-16 text-sm leading-relaxed text-text-secondary">
                        {pair[index].tagline}
                      </p>
                      {pair[index].description && (
                        <p className="mt-4 line-clamp-3 text-xs leading-relaxed text-text-muted">
                          {pair[index].description}
                        </p>
                      )}
                      <span
                        className={cn(
                          "mt-8 flex w-full items-center justify-center gap-2 rounded-full border py-3 text-sm font-medium transition-colors group-hover:border-accent group-hover:bg-accent-dim group-hover:text-accent",
                          pending === side && "bg-accent-dim text-accent",
                        )}
                      >
                        {pending === side ? (
                          <>
                            <Loader2 className="size-4 animate-spin" />
                            Saving comparison…
                          </>
                        ) : (
                          <>
                            {side === "left" ? (
                              <ArrowLeft className="size-4" />
                            ) : null}
                            This project wins
                            {side === "right" ? (
                              <ArrowRight className="size-4" />
                            ) : null}
                          </>
                        )}
                      </span>
                    </motion.button>
                    <div className="border-t bg-bg/50 px-6 py-4 sm:px-8">
                      <Link
                        href={`/gallery/${pair[index].id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-link text-xs text-text-secondary"
                      >
                        Explore project
                        <ArrowUpRight className="size-3.5" />
                        <span className="sr-only"> opens in a new tab</span>
                      </Link>
                    </div>
                  </article>
                ))}
                <div className="row-start-2 flex flex-col items-center justify-center gap-3 py-2 md:col-start-2 md:row-start-1">
                  <span className="hidden font-mono text-xs tracking-widest text-text-muted md:block">
                    OR
                  </span>
                  <Button
                    variant="outline"
                    disabled={pending !== null}
                    onClick={() => void choose("tie")}
                    className="h-12 gap-2 px-5 md:size-16 md:flex-col md:gap-1 md:p-0"
                  >
                    {pending === "tie" ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Equal className="size-5" />
                    )}
                    <span className="text-xs">Tie</span>
                  </Button>
                </div>
              </motion.div>
            </AnimatePresence>
            <p className="mt-6 text-center text-xs leading-relaxed text-text-muted">
              Each choice is saved before the next pair appears. Take your time;
              thoughtful comparisons make a stronger ranking.
            </p>
          </>
        )
      )}
    </div>
  );
}

function PairwiseSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading comparison projects"
      className="grid gap-6 md:grid-cols-2"
    >
      <span className="sr-only">Loading projects…</span>
      {[0, 1].map((index) => (
        <div key={index} className="surface p-8">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="mt-8 h-36 w-full rounded-xl" />
          <Skeleton className="mt-7 h-8 w-3/4" />
          <Skeleton className="mt-4 h-4 w-full" />
          <Skeleton className="mt-3 h-4 w-2/3" />
          <Skeleton className="mt-8 h-12 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}
