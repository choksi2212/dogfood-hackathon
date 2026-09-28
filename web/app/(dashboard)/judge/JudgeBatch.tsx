"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  CheckCheck,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { ClientDate } from "@/components/client-date";
import { EmptyState, PageHeading, ProgressRing } from "@/components/portal-ui";
import { cn } from "@/lib/cn";
import type { BatchProject, MyBatchResponse } from "@/lib/api/types";

type Filter = "all" | "pending" | "reviewed";

export function JudgeBatch({
  projects,
  progress,
}: {
  projects: BatchProject[];
  progress: MyBatchResponse["progress"];
}) {
  const reducedMotion = useReducedMotion();
  const [filter, setFilter] = useState<Filter>("all");
  const pending = projects.filter((project) => !project.reviewed);
  const visible = projects.filter(
    (project) =>
      filter === "all" ||
      (filter === "reviewed" ? project.reviewed : !project.reviewed),
  );
  const nextProject = pending[0];

  return (
    <div>
      <PageHeading
        eyebrow="JUDGING / YOUR WORKSPACE"
        title="Your batch"
        description="Fresh ideas deserve a fair look. Review your assigned projects, one thoughtful score at a time."
      />
      <section
        className="surface relative mb-8 flex flex-wrap items-center justify-between gap-6 overflow-hidden p-6 sm:p-8"
        aria-label="Review progress"
      >
        <div
          className="pointer-events-none absolute -right-20 -top-32 size-80 rounded-full bg-accent/10 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative flex flex-wrap items-center gap-6 sm:flex-nowrap">
          <ProgressRing value={progress.scored} total={progress.total} />
          <div>
            <p className="eyebrow mb-2">YOUR PROGRESS</p>
            <h2 className="text-xl font-medium tracking-tight sm:text-2xl">
              {projects.length === 0
                ? "A clean slate."
                : nextProject
                  ? "Keep the momentum going."
                  : "Every review is in."}
            </h2>
            <p className="mt-2 text-sm text-text-secondary">
              {projects.length === 0
                ? "Your assigned projects will appear here."
                : nextProject
                  ? `${pending.length} ${pending.length === 1 ? "project" : "projects"} waiting for your perspective.`
                  : "Thank you for giving these ideas your attention."}
            </p>
          </div>
        </div>
        {nextProject ? (
          <Link
            href={`/judge/${nextProject.id}`}
            className={cn(buttonVariants(), "relative")}
          >
            Continue judging
            <ArrowRight className="size-4" />
          </Link>
        ) : projects.length > 0 ? (
          <Badge className="relative h-auto gap-2 bg-success-dim px-4 py-2 text-success">
            <CheckCheck />
            Batch complete
          </Badge>
        ) : null}
      </section>
      {projects.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="No projects assigned yet"
          description="Your organizer is preparing the judging batch. Assigned projects will appear here when they’re ready."
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-lg font-medium tracking-tight">
              Assigned projects{" "}
              <span className="ml-2 font-mono text-sm text-text-muted">
                {projects.length}
              </span>
            </h2>
            <div
              className="flex rounded-full border bg-bg-elevated p-1"
              role="group"
              aria-label="Filter assigned projects"
            >
              {(["all", "pending", "reviewed"] as const).map((option) => (
                <Button
                  key={option}
                  size="sm"
                  variant="ghost"
                  aria-pressed={filter === option}
                  className={cn(
                    "rounded-full px-4 text-xs capitalize",
                    filter === option &&
                      "bg-accent-dim text-accent hover:bg-accent-dim hover:text-accent",
                  )}
                  onClick={() => setFilter(option)}
                >
                  {option}
                </Button>
              ))}
            </div>
          </div>
          {visible.length === 0 ? (
            <EmptyState
              icon={filter === "pending" ? CheckCheck : ClipboardCheck}
              title={
                filter === "pending"
                  ? "You’re all caught up"
                  : "Your first review starts here"
              }
              description={
                filter === "pending"
                  ? "Every assigned project has a submitted review."
                  : "Switch to pending projects to start reviewing your batch."
              }
            />
          ) : (
            <motion.ul
              initial="hidden"
              animate="visible"
              variants={{
                hidden: {},
                visible: {
                  transition: { staggerChildren: reducedMotion ? 0 : 0.06 },
                },
              }}
              className="space-y-3"
            >
              {visible.map((project, index) => (
                <motion.li
                  key={project.id}
                  variants={{
                    hidden: {
                      opacity: reducedMotion ? 1 : 0,
                      y: reducedMotion ? 0 : 8,
                    },
                    visible: {
                      opacity: 1,
                      y: 0,
                      transition: { duration: 0.3 },
                    },
                  }}
                >
                  <div className="surface interactive-card flex flex-wrap items-center gap-5 p-5 sm:flex-nowrap sm:p-6">
                    <div
                      className={cn(
                        "flex size-11 shrink-0 items-center justify-center rounded-xl font-mono text-sm",
                        project.reviewed
                          ? "bg-success-dim text-success"
                          : "bg-accent-dim text-accent",
                      )}
                    >
                      {project.reviewed ? (
                        <CheckCircle2 className="size-5" />
                      ) : (
                        String(index + 1).padStart(2, "0")
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/judge/${project.id}`}
                        className="text-link text-lg font-medium tracking-tight"
                      >
                        {project.name}
                      </Link>
                      <p className="mt-1 text-sm leading-relaxed text-text-secondary">
                        {project.tagline}
                      </p>
                      {project.reviewed && project.submitted_at && (
                        <p className="mt-2 flex items-center gap-1.5 text-xs text-text-muted">
                          <Clock3 className="size-3" />
                          <span>
                            Reviewed{" "}
                            <ClientDate
                              iso={project.submitted_at}
                              className="font-mono"
                            />
                          </span>
                        </p>
                      )}
                    </div>
                    <div className="flex w-full shrink-0 items-center justify-between gap-3 border-t pt-4 sm:w-auto sm:justify-start sm:border-0 sm:pt-0">
                      <Badge
                        variant="outline"
                        className={cn(
                          "h-auto border-transparent py-1",
                          project.reviewed
                            ? "bg-success-dim text-success"
                            : "bg-bg-overlay text-text-secondary",
                        )}
                      >
                        {project.reviewed ? "Reviewed" : "Pending"}
                      </Badge>
                      <Link
                        href={`/judge/${project.id}`}
                        className={cn(
                          buttonVariants({
                            variant: project.reviewed ? "ghost" : "outline",
                            size: "sm",
                          }),
                          "rounded-full",
                        )}
                      >
                        {project.reviewed ? "View review" : "Continue judging"}
                        <ArrowRight className="size-3.5" />
                      </Link>
                    </div>
                  </div>
                </motion.li>
              ))}
            </motion.ul>
          )}
        </>
      )}
    </div>
  );
}
