"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Check, Heart, HelpCircle, Loader2, ArrowUpRight } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { api, ApiError } from "@/lib/api/client";
import type { Submission } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { EmptyState, PageHeading } from "@/components/portal-ui";
import { RouteError } from "@/components/route-error";
import { RouteLoading } from "@/components/route-loading";

export default function VotePage() {
  const [items, setItems] = useState<Submission[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [voted, setVoted] = useState<Record<string, boolean>>({});
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const busy = useRef(new Set<string>());
  const reduced = useReducedMotion();
  useEffect(() => {
    let active = true;
    api
      .allGallery()
      .then((data) => {
        if (active) setItems(data);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [retry]);
  async function toggle(id: string) {
    if (busy.current.has(id)) return;
    busy.current.add(id);
    const previous = voted[id] ?? false;
    setVoted((prev) => ({ ...prev, [id]: !previous }));
    setPending((prev) => ({ ...prev, [id]: true }));
    setErrors((prev) => ({ ...prev, [id]: "" }));
    try {
      if (previous) await api.retractVote(id);
      else await api.vote(id);
    } catch (err) {
      setVoted((prev) => ({ ...prev, [id]: previous }));
      setErrors((prev) => ({
        ...prev,
        [id]:
          err instanceof ApiError
            ? err.message
            : "Your vote couldn’t be saved. Please try again.",
      }));
    } finally {
      busy.current.delete(id);
      setPending((prev) => ({ ...prev, [id]: false }));
    }
  }
  return (
    <div>
      <PageHeading
        eyebrow="COMMUNITY / YOUR VOICE COUNTS"
        title="Community voting"
        description="Meet the builders. Explore their work. Give a little recognition to the projects that deserve it."
        action={
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger
                aria-label="How voting works"
                className="flex size-11 items-center justify-center rounded-full border bg-bg-elevated"
              >
                <HelpCircle className="size-5 text-text-secondary" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs p-4 leading-relaxed">
                Cast one vote per project, or retract it at any time. The
                event’s voting mode sets how votes are counted. Votes shown on
                this page reflect this visit.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        }
      />
      {failed ? (
        <RouteError
          message="Could not load voting projects"
          reset={() => {
            setFailed(false);
            setItems(null);
            setRetry((v) => v + 1);
          }}
        />
      ) : !items ? (
        <RouteLoading cards />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="Great work is on the way"
          description="Voting opens up as soon as the first projects are submitted."
        />
      ) : (
        <>
          <div className="mb-6 flex items-center justify-between rounded-xl border bg-bg-elevated px-5 py-4">
            <p className="text-sm text-text-secondary">
              <span className="font-mono text-text-primary">
                {items.length}
              </span>{" "}
              projects to discover
            </p>
            <span className="font-mono text-xs text-accent">
              {Object.values(voted).filter(Boolean).length} backed this visit
            </span>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item, i) => (
              <motion.article
                key={item.id}
                initial={reduced ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: Math.min(i, 5) * 0.05 }}
                className="interactive-card surface flex flex-col p-6"
              >
                <div className="mb-7 flex items-center justify-between gap-2">
                  <span className="flex size-11 items-center justify-center rounded-xl bg-accent-dim font-mono text-sm text-accent">
                    {item.name.slice(0, 2).toUpperCase()}
                  </span>
                  <Badge variant="secondary">{item.track_slug}</Badge>
                </div>
                <Link
                  href={`/gallery/${item.id}`}
                  className="group text-xl leading-tight font-medium tracking-tight hover:text-accent"
                >
                  <span>{item.name}</span>
                  <ArrowUpRight className="ml-1 inline size-4 text-text-muted group-hover:text-accent" />
                </Link>
                <p className="mt-3 mb-7 text-sm leading-relaxed text-text-secondary">
                  {item.tagline}
                </p>
                <div className="mt-auto border-t pt-5">
                  <Button
                    onClick={() => toggle(item.id)}
                    disabled={pending[item.id]}
                    variant={voted[item.id] ? "default" : "outline"}
                    className="w-full"
                    aria-pressed={voted[item.id] ?? false}
                    aria-label={
                      voted[item.id]
                        ? `Retract vote for ${item.name}`
                        : `Vote for ${item.name}`
                    }
                  >
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.span
                        key={voted[item.id] ? "voted" : "idle"}
                        initial={reduced ? false : { opacity: 0, y: 3 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduced ? undefined : { opacity: 0, y: -3 }}
                        transition={{ duration: 0.15 }}
                        className="inline-flex items-center gap-2"
                      >
                        {pending[item.id] ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : voted[item.id] ? (
                          <Check className="size-4" />
                        ) : (
                          <Heart className="size-4" />
                        )}
                        {voted[item.id] ? "Voted" : "Vote for project"}
                      </motion.span>
                    </AnimatePresence>
                  </Button>
                  {voted[item.id] && !pending[item.id] && (
                    <p className="mt-2 text-center text-xs text-text-muted">
                      Click again to retract
                    </p>
                  )}
                  {errors[item.id] && (
                    <p
                      role="alert"
                      className="mt-3 text-xs leading-relaxed text-error"
                    >
                      {errors[item.id]}
                    </p>
                  )}
                </div>
              </motion.article>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
