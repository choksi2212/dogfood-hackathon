"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Loader2,
  Pencil,
  Save,
  Send,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ClientDate } from "@/components/client-date";
import { EmptyState } from "@/components/portal-ui";
import { cn } from "@/lib/cn";
import type { RubricResponse } from "@/lib/api/types";

type Criterion = RubricResponse["criteria"][number];
type Status = "idle" | "saving" | "submitting";

function actionError(error: unknown, action: "save" | "submit") {
  if (error instanceof ApiError && error.status === 403)
    return "This review can’t be changed right now. Check that judging is open and that this account is assigned to the project.";
  return action === "save"
    ? "Your draft couldn’t be saved. Your changes are still here; please try again."
    : "Your review couldn’t be submitted. Your saved draft is safe; please try again.";
}

export function ScoreForm({
  projectId,
  criteria,
  initialValues = {},
  initialSubmittedAt = null,
}: {
  projectId: string;
  criteria: Criterion[];
  initialValues?: Record<string, number>;
  initialSubmittedAt?: string | null;
}) {
  const router = useRouter();
  const reducedMotion = useReducedMotion();
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(
      criteria.map((criterion) => [
        criterion.id,
        initialValues[criterion.id] ?? criterion.min,
      ]),
    ),
  );
  const [comments, setComments] = useState<Record<string, string>>({});
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submittedAt, setSubmittedAt] = useState<string | null>(
    initialSubmittedAt,
  );
  const inFlight = useRef(false);
  const busy = status !== "idle";

  function markChanged() {
    setSaved(false);
    setError(null);
  }
  function setValue(criterionId: string, value: number) {
    setValues((previous) => ({ ...previous, [criterionId]: value }));
    markChanged();
  }

  async function persistDraft() {
    const criterionComments = criteria
      .filter((criterion) => comments[criterion.id]?.trim())
      .map(
        (criterion) => `${criterion.name}: ${comments[criterion.id].trim()}`,
      );
    const combinedComment = [
      ...criterionComments,
      ...(comment.trim() ? [`Overall feedback: ${comment.trim()}`] : []),
    ].join("\n\n");
    await api.saveScore(projectId, {
      scores: criteria.map((criterion) => ({
        criterion_id: criterion.id,
        value: values[criterion.id] ?? criterion.min,
      })),
      ...(combinedComment ? { comment: combinedComment } : {}),
    });
    setSaved(true);
  }

  async function handleSave() {
    if (inFlight.current) return;
    inFlight.current = true;
    setStatus("saving");
    setError(null);
    try {
      await persistDraft();
    } catch (failure) {
      setError(actionError(failure, "save"));
    } finally {
      inFlight.current = false;
      setStatus("idle");
    }
  }

  async function handleSubmit() {
    if (inFlight.current) return;
    inFlight.current = true;
    setStatus("submitting");
    setError(null);
    let draftSaved = false;
    try {
      await persistDraft();
      draftSaved = true;
      const result = await api.submitScore(projectId);
      setSubmittedAt(result.submitted_at);
      router.refresh();
    } catch (failure) {
      setError(actionError(failure, draftSaved ? "submit" : "save"));
    } finally {
      inFlight.current = false;
      setStatus("idle");
    }
  }

  if (submittedAt)
    return (
      <motion.section
        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="surface overflow-hidden p-8 sm:p-10"
        aria-live="polite"
      >
        <span className="mb-8 flex size-16 items-center justify-center rounded-2xl bg-success-dim text-success">
          <CheckCircle2 className="size-8" />
        </span>
        <p className="eyebrow text-success">REVIEW SUBMITTED</p>
        <h2 className="mt-3 text-3xl font-medium tracking-display">
          Your perspective is in.
        </h2>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          Your scores have been submitted. Continue with your batch, or revisit
          this review while judging is open.
        </p>
        <p className="mt-6 rounded-xl border bg-bg p-4 text-xs text-text-secondary">
          Submitted <ClientDate iso={submittedAt} className="font-mono" />
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/judge" className={buttonVariants()}>
            Back to your batch
            <ArrowRight className="size-4" />
          </Link>
          <Button variant="outline" onClick={() => setSubmittedAt(null)}>
            <Pencil className="size-4" />
            Edit review
          </Button>
        </div>
      </motion.section>
    );

  if (criteria.length === 0)
    return (
      <EmptyState
        icon={ClipboardList}
        title="The rubric is being prepared"
        description="Your organizer hasn’t added scoring criteria yet. Come back when the judging rubric is ready."
        href="/judge"
        action="Back to your batch"
      />
    );

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void handleSubmit();
      }}
      className="surface overflow-hidden"
      aria-label="Project scoring form"
    >
      <div className="flex items-start justify-between gap-4 border-b bg-accent-dim/40 p-6 sm:p-7">
        <div>
          <p className="eyebrow mb-2">THE RUBRIC</p>
          <h2 className="text-xl font-medium tracking-tight">
            Make your assessment.
          </h2>
          <p className="mt-2 text-sm text-text-secondary">
            Score each criterion. Leave a little context.
          </p>
        </div>
        <Badge
          variant="outline"
          className="mt-1 h-auto shrink-0 bg-bg-elevated py-1 font-mono text-xs"
        >
          {criteria.length} criteria
        </Badge>
      </div>
      <div className="space-y-5 p-6 sm:p-7">
        {criteria.map((criterion, index) => {
          const value = values[criterion.id] ?? criterion.min;
          const labelId = `criterion-${criterion.id}`;
          const descriptionId = `criterion-description-${criterion.id}`;
          return (
            <fieldset
              key={criterion.id}
              disabled={busy}
              className="rounded-xl border bg-bg p-5 sm:p-6"
            >
              <legend className="sr-only">{criterion.name}</legend>
              <div className="mb-3 flex items-start justify-between gap-4">
                <Label
                  id={labelId}
                  htmlFor={`score-${criterion.id}`}
                  className="flex items-center gap-3 text-base font-medium"
                >
                  <span className="font-mono text-xs text-text-muted">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {criterion.name}
                </Label>
                <Badge
                  variant="outline"
                  className="h-auto bg-bg-overlay py-1 font-mono text-xs text-text-secondary"
                >
                  weight {criterion.weight}
                </Badge>
              </div>
              {criterion.description && (
                <p
                  id={descriptionId}
                  className="mb-6 text-sm leading-relaxed text-text-secondary"
                >
                  {criterion.description}
                </p>
              )}
              <div className="flex items-center gap-5">
                <div className="flex-1">
                  <Slider
                    id={`score-${criterion.id}`}
                    aria-labelledby={labelId}
                    aria-describedby={
                      criterion.description ? descriptionId : undefined
                    }
                    aria-label={`${criterion.name} score`}
                    min={criterion.min}
                    max={criterion.max}
                    step={1}
                    value={[value]}
                    disabled={busy}
                    onValueChange={(next) =>
                      setValue(
                        criterion.id,
                        Array.isArray(next) ? next[0] : next,
                      )
                    }
                    className="py-3 [&_[data-slot=slider-track]]:h-1.5 [&_[data-slot=slider-thumb]]:size-4 [&_[data-slot=slider-thumb]]:border-2"
                  />
                  <div className="mt-1 flex justify-between font-mono text-xs text-text-muted">
                    <span>{criterion.min} · minimum</span>
                    <span>{criterion.max} · maximum</span>
                  </div>
                </div>
                <motion.output
                  key={value}
                  htmlFor={`score-${criterion.id}`}
                  initial={reducedMotion ? false : { scale: 0.94 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.2 }}
                  className="flex size-16 shrink-0 flex-col items-center justify-center rounded-xl border border-accent/25 bg-accent-dim font-mono text-2xl tabular-nums text-accent"
                >
                  {value}
                  <span className="text-xs text-text-secondary">
                    / {criterion.max}
                  </span>
                </motion.output>
              </div>
              <div className="mt-6">
                <Label
                  htmlFor={`feedback-${criterion.id}`}
                  className="mb-2 text-xs text-text-secondary"
                >
                  Feedback on {criterion.name}{" "}
                  <span className="text-text-muted">(optional)</span>
                </Label>
                <Textarea
                  id={`feedback-${criterion.id}`}
                  value={comments[criterion.id] ?? ""}
                  onChange={(event) => {
                    setComments((previous) => ({
                      ...previous,
                      [criterion.id]: event.target.value,
                    }));
                    markChanged();
                  }}
                  rows={2}
                  placeholder="What worked well? What could go further?"
                  className="resize-y text-sm"
                />
              </div>
            </fieldset>
          );
        })}
        <div className="pt-1">
          <Label htmlFor="overall-feedback" className="mb-2 text-sm">
            Overall feedback{" "}
            <span className="text-xs text-text-muted">(optional)</span>
          </Label>
          <Textarea
            id="overall-feedback"
            value={comment}
            disabled={busy}
            onChange={(event) => {
              setComment(event.target.value);
              markChanged();
            }}
            rows={3}
            placeholder="Share a final thought with the team."
          />
        </div>
        {error && (
          <Alert variant="destructive" role="alert">
            <AlertCircle className="size-4" />
            <AlertTitle>Review needs your attention</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>
      <div className="border-t bg-bg/50 p-6 sm:p-7">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => void handleSave()}
          >
            {status === "saving" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            {status === "saving" ? "Saving draft…" : "Save draft"}
          </Button>
          <Button type="submit" disabled={busy}>
            {status === "submitting" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            {status === "submitting" ? "Submitting…" : "Submit review"}
          </Button>
          {saved && !busy && !error && (
            <span
              className="flex items-center gap-1.5 text-xs text-success"
              role="status"
            >
              <CheckCircle2 className="size-3.5" />
              Draft saved
            </span>
          )}
        </div>
        <p
          className={cn(
            "mt-4 text-xs leading-relaxed text-text-muted",
            busy && "opacity-70",
          )}
        >
          Save a draft to pick this up later. Submit when your assessment is
          complete.
        </p>
      </div>
    </form>
  );
}
