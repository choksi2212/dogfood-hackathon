"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowUpRight,
  Check,
  Code2,
  Copy,
  Globe2,
  Layers3,
  PlugZap,
  RotateCcw,
} from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import type { WidgetGalleryResponse } from "@/lib/api/types";
import { PageHeading, EmptyState } from "@/components/portal-ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

export default function WidgetPage() {
  const reducedMotion = useReducedMotion();
  const codeRef = useRef<HTMLElement>(null);
  const copyTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [data, setData] = useState<WidgetGalleryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "selected">(
    "idle",
  );
  const scriptUrl = api.widgetScriptUrl();
  const snippet = [
    '<div id="dogfood-widget"></div>',
    "<script>",
    "  window.DOGFOOD_WIDGET = {",
    `    event: "${EVENT_SLUG}",`,
    '    target: document.getElementById("dogfood-widget"),',
    "  };",
    "</" + "script>",
    `<script src="${scriptUrl}"></` + "script>",
  ].join("\n");

  useEffect(() => {
    let active = true;
    api
      .widgetGallery()
      .then((response) => {
        if (!Array.isArray(response.items))
          throw new Error("Widget feed unavailable");
        if (active) {
          setData(response);
          setFailed(false);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setFailed(true);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  useEffect(
    () => () => {
      if (copyTimeout.current) clearTimeout(copyTimeout.current);
    },
    [],
  );

  function retry() {
    setLoading(true);
    setFailed(false);
    setAttempt((value) => value + 1);
  }
  async function copySnippet() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopyState("copied");
      if (copyTimeout.current) clearTimeout(copyTimeout.current);
      copyTimeout.current = setTimeout(() => setCopyState("idle"), 2500);
    } catch {
      if (codeRef.current) {
        const range = document.createRange();
        range.selectNodeContents(codeRef.current);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
      setCopyState("selected");
    }
  }

  return (
    <div>
      <PageHeading
        eyebrow="LEDGER / EVERYWHERE"
        title="Bring the builds to your site."
        description="A little window into everything that shipped. Embed the live gallery on your event page, community hub, or team website."
        action={
          <Badge
            variant="outline"
            className="h-8 gap-2 border-accent/25 bg-accent-dim px-3 text-accent"
          >
            <Globe2 className="size-3.5" />
            Public, no sign-in needed
          </Badge>
        }
      />
      <div className="grid items-start gap-8 lg:grid-cols-[1fr_1fr]">
        <section className="overflow-hidden rounded-2xl border border-border bg-bg-elevated shadow-card">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <span className="flex gap-1.5" aria-hidden="true">
                <span className="size-2 rounded-full bg-border-strong" />
                <span className="size-2 rounded-full bg-border-strong" />
                <span className="size-2 rounded-full bg-border-strong" />
              </span>
              <span className="ml-2">Live preview</span>
            </div>
            <span className="flex items-center gap-2 font-mono text-xs text-text-muted">
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  loading ? "bg-warning" : failed ? "bg-error" : "bg-success",
                )}
              />
              {loading ? "CONNECTING" : failed ? "UNAVAILABLE" : "CONNECTED"}
            </span>
          </div>
          <div className="p-5 sm:p-7">
            <div className="mb-6 flex items-start justify-between gap-3">
              <div>
                <p className="eyebrow text-xs">LEDGER / 2026</p>
                <h2 className="mt-2 text-2xl font-medium tracking-tight">
                  Fresh from the hackathon.
                </h2>
                <p className="mt-2 text-xs leading-relaxed text-text-muted">
                  Real projects. Big ideas. Ready to explore.
                </p>
              </div>
              <Layers3
                className="mt-1 size-7 shrink-0 text-accent"
                strokeWidth={1.25}
              />
            </div>
            {loading ? (
              <div
                role="status"
                aria-label="Loading widget gallery"
                className="grid gap-3 sm:grid-cols-2"
              >
                <span className="sr-only">Loading widget gallery…</span>
                {Array.from({ length: 6 }, (_, index) => (
                  <div
                    key={index}
                    className="rounded-xl border border-border bg-bg p-5"
                  >
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="mt-5 h-5 w-full" />
                    <Skeleton className="mt-3 h-3 w-4/5" />
                    <Skeleton className="mt-3 h-3 w-2/3" />
                  </div>
                ))}
              </div>
            ) : failed ? (
              <Alert variant="destructive">
                <PlugZap className="size-4" />
                <AlertTitle>The gallery feed is unavailable</AlertTitle>
                <AlertDescription>
                  <p>
                    We couldn’t connect to the live gallery. Try again in a
                    moment.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={retry}
                    className="mt-4"
                  >
                    <RotateCcw className="size-3.5" />
                    Retry preview
                  </Button>
                </AlertDescription>
              </Alert>
            ) : data?.items.length ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {data.items.slice(0, 6).map((project, index) => (
                  <motion.div
                    key={project.id}
                    initial={reducedMotion ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.3,
                      delay: reducedMotion ? 0 : index * 0.05,
                    }}
                    whileHover={reducedMotion ? undefined : { y: -2 }}
                  >
                    <Link
                      href={`/gallery/${encodeURIComponent(project.id)}`}
                      className="group block h-full rounded-xl border border-border bg-bg p-5 transition-colors hover:border-accent/40 hover:bg-accent-dim"
                    >
                      <Badge
                        variant="outline"
                        className="max-w-full border-accent/20 bg-accent-dim text-xs text-accent"
                      >
                        {project.track_slug}
                      </Badge>
                      <div className="mt-4 flex items-start justify-between gap-2">
                        <h3 className="text-sm leading-tight font-medium tracking-tight">
                          {project.name}
                        </h3>
                        <ArrowUpRight className="size-3.5 shrink-0 text-text-muted transition-colors group-hover:text-accent" />
                      </div>
                      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-text-secondary">
                        {project.tagline}
                      </p>
                    </Link>
                  </motion.div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Layers3}
                title="The first build is on its way"
                description="Published submissions will appear here as soon as they join the gallery."
              />
            )}
            <div className="mt-6 flex items-center justify-between gap-3 border-t border-border pt-5">
              <span className="font-mono text-xs text-text-muted">
                {data
                  ? `${data.items.length} PROJECTS IN THE FEED`
                  : "LIVE GALLERY FEED"}
              </span>
              <Link
                href="/gallery"
                className="inline-flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover"
              >
                Explore gallery
                <ArrowUpRight className="size-3" />
              </Link>
            </div>
          </div>
        </section>
        <div className="space-y-6">
          <section className="overflow-hidden rounded-2xl border border-border bg-bg-elevated shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-5 sm:px-7">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-accent-dim text-accent">
                  <Code2 className="size-4" />
                </span>
                <div>
                  <h2 className="text-sm font-medium">Your embed code</h2>
                  <p className="mt-1 font-mono text-xs text-text-muted">
                    HTML · READY TO PASTE
                  </p>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={copySnippet}>
                {copyState === "copied" ? (
                  <>
                    <Check className="size-3.5 text-success" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="size-3.5" />
                    Copy code
                  </>
                )}
              </Button>
            </div>
            <pre className="overflow-x-auto bg-bg p-5 font-mono text-xs leading-[1.9] text-text-secondary sm:p-7">
              <code ref={codeRef}>{snippet}</code>
            </pre>
            <p
              aria-live="polite"
              className={cn(
                "border-t border-border px-5 py-4 text-xs leading-relaxed sm:px-7",
                copyState === "copied" ? "text-success" : "text-text-muted",
              )}
            >
              {copyState === "copied"
                ? "Copied. You’re ready to add the gallery to your site."
                : copyState === "selected"
                  ? "Code selected. Press Ctrl+C (or ⌘C) to copy it."
                  : "Add this snippet wherever you want the gallery to appear."}
            </p>
          </section>
          <section className="rounded-2xl border border-border bg-bg-elevated p-6 sm:p-7">
            <p className="eyebrow">THREE STEPS. ONE LIVE GALLERY.</p>
            <ol className="mt-5 space-y-5">
              {[
                {
                  title: "Copy your snippet",
                  body: "The event and gallery target are already included.",
                },
                {
                  title: "Add it to your page",
                  body: "Paste the HTML where visitors should discover the projects.",
                },
                {
                  title: "Let the builds speak",
                  body: "Your widget loads the published gallery whenever the page opens.",
                },
              ].map((step, index) => (
                <li key={step.title} className="flex items-start gap-4">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-accent/25 bg-accent-dim font-mono text-xs text-accent">
                    0{index + 1}
                  </span>
                  <div>
                    <h3 className="text-sm font-medium">{step.title}</h3>
                    <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">
                      {step.body}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
