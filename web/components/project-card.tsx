"use client";
import Link from "next/link";
import { ArrowUpRight, Code2 } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { ClientDate } from "@/components/client-date";
import type { Submission } from "@/lib/api/types";

export function ProjectCard({
  item,
  index = 0,
}: {
  item: Submission;
  index?: number;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.article
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index, 5) * 0.05 }}
      className="h-full"
    >
      <Link
        href={`/gallery/${item.id}`}
        className="interactive-card group flex h-full flex-col rounded-xl border bg-bg-elevated"
      >
        <div className="project-art relative flex h-36 items-end justify-between overflow-hidden border-b p-5">
          <span className="flex size-12 items-center justify-center rounded-xl border border-border-strong bg-bg/70 font-mono text-lg text-accent">
            {item.name.slice(0, 2).toUpperCase()}
          </span>
          <Code2 className="relative z-10 size-5 text-text-muted" />
          <Badge
            variant="secondary"
            className="absolute top-4 left-4 z-10 bg-bg/80 text-xs"
          >
            {item.track_slug}
          </Badge>
        </div>
        <div className="flex flex-1 flex-col p-6">
          <h3 className="text-xl leading-tight font-medium tracking-tight transition-colors group-hover:text-accent-hover">
            {item.name}
          </h3>
          <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-text-secondary">
            {item.tagline || "Explore this hackathon submission."}
          </p>
          <div className="mt-auto flex items-center justify-between gap-2 pt-6">
            <span className="font-mono text-xs text-text-muted">
              <ClientDate iso={item.submitted_at} variant="short" />
            </span>
            <span className="flex items-center gap-1 text-xs font-medium text-accent">
              View project
              <ArrowUpRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </span>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}
