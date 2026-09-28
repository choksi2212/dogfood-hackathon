"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Download,
  GitBranch,
  Loader2,
  MailPlus,
  Scale,
  X,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { AssignmentRunResponse, NormalizeResponse } from "@/lib/api/types";

type Status = "idle" | "loading" | "error";
const ToastContext = createContext<(message: string) => void>(() => undefined);

function actionError(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.status === 401)
      return "Your session has expired. Sign in again to continue.";
    if (error.status === 403)
      return "This operation requires an organizer account.";
    if (error.status === 429)
      return "Too many requests. Wait a moment, then try again.";
    if (error.status === 400 || error.status === 409)
      return fallback + " Check the event setup and try again.";
  }
  return fallback + " Please try again.";
}

function ActionCard({
  icon: Icon,
  label,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  label: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      whileHover={reducedMotion ? undefined : { y: -2 }}
      transition={{ duration: 0.2 }}
      className="surface interactive-card flex h-full flex-col rounded-2xl p-6"
    >
      <div className="mb-5 flex items-center justify-between">
        <span className="flex size-11 items-center justify-center rounded-xl border border-accent/20 bg-accent-dim text-accent">
          <Icon className="size-5" />
        </span>
        <span className="font-mono text-xs tracking-widest text-text-muted uppercase">
          {label}
        </span>
      </div>
      <h3 className="text-lg font-medium tracking-tight">{title}</h3>
      <p className="mt-2 mb-6 text-sm leading-relaxed text-text-secondary">
        {description}
      </p>
      {children}
    </motion.div>
  );
}

function ActionFailure({ error }: { error: string | null }) {
  return error ? (
    <Alert variant="destructive" role="alert" className="mt-4">
      <AlertCircle className="size-4" />
      <AlertTitle>Operation couldn’t complete</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  ) : null;
}

function BusyIcon() {
  const reducedMotion = useReducedMotion();
  return (
    <Loader2
      aria-hidden="true"
      className={cn("size-4", !reducedMotion && "animate-spin")}
    />
  );
}

export function OrganizerActions() {
  const [toast, setToast] = useState<{ text: string; key: number } | null>(
    null,
  );
  const reducedMotion = useReducedMotion();
  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(timeout);
  }, [toast]);
  return (
    <ToastContext.Provider
      value={(text) => setToast({ text, key: Date.now() })}
    >
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <BulkInvitePanel />
        <AssignmentPanel />
        <NormalizationPanel />
      </div>
      <div className="surface mt-6 flex flex-wrap items-center justify-between gap-5 rounded-xl px-6 py-5">
        <div className="flex items-center gap-4">
          <span className="flex size-10 items-center justify-center rounded-lg bg-bg-overlay text-text-secondary">
            <Download className="size-5" />
          </span>
          <div>
            <h3 className="text-sm font-medium">Take the scores with you</h3>
            <p className="mt-1 text-xs text-text-secondary">
              Download a CSV for independent review and reporting.
            </p>
          </div>
        </div>
        <a
          href={api.csvExportUrl()}
          download
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          <Download className="size-4" />
          Export scores
        </a>
      </div>
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.key}
            initial={reducedMotion ? false : { opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: 8 }}
            transition={{ duration: 0.25 }}
            className="fixed right-4 bottom-5 z-50 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-success/30 bg-bg-elevated p-4 shadow-elevated sm:right-8"
          >
            <CheckCircle2 className="size-5 shrink-0 text-success" />
            <p role="status" aria-live="polite" className="text-sm">
              {toast.text}
            </p>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              aria-label="Dismiss notification"
              onClick={() => setToast(null)}
            >
              <X className="size-4" />
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </ToastContext.Provider>
  );
}

export function BulkInvitePanel() {
  const router = useRouter();
  const notify = useContext(ToastContext);
  const [emails, setEmails] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [invited, setInvited] = useState<number | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const list = [
      ...new Set(
        emails
          .split(/[\n,]/)
          .map((email) => email.trim())
          .filter(Boolean),
      ),
    ];
    if (
      !list.length ||
      list.some((email) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    ) {
      setError(
        "Enter valid email addresses, separated by commas or new lines.",
      );
      setStatus("error");
      return;
    }
    setStatus("loading");
    setError(null);
    setInvited(null);
    try {
      const result = await api.bulkInviteJudges(list);
      setInvited(result.invited);
      setEmails("");
      setStatus("idle");
      notify(
        `${result.invited} judge${result.invited === 1 ? "" : "s"} invited successfully.`,
      );
      router.refresh();
    } catch (err) {
      setStatus("error");
      setError(actionError(err, "We couldn’t invite these judges."));
    }
  }

  return (
    <ActionCard
      icon={MailPlus}
      label="01 / PEOPLE"
      title="Bulk invite judges"
      description="Build your judging panel in one go. Add an email address per line, or separate them with commas."
    >
      <form onSubmit={handleSubmit} className="flex flex-1 flex-col">
        <Label
          htmlFor="invite-emails"
          className="mb-2 text-xs text-text-secondary"
        >
          Judge email addresses
        </Label>
        <Textarea
          id="invite-emails"
          value={emails}
          onChange={(e) => setEmails(e.target.value)}
          rows={4}
          placeholder="Add judge email addresses…"
          required
          disabled={status === "loading"}
          aria-invalid={status === "error"}
          aria-describedby={error ? "invite-error" : undefined}
          className="min-h-28 resize-none bg-bg-overlay text-sm"
        />
        <Button
          type="submit"
          disabled={status === "loading" || !emails.trim()}
          className="mt-4 w-full"
          aria-busy={status === "loading"}
        >
          {status === "loading" ? (
            <BusyIcon />
          ) : (
            <MailPlus className="size-4" />
          )}
          {status === "loading" ? "Sending invites…" : "Invite judges"}
        </Button>
        {invited !== null && (
          <div
            role="status"
            className="mt-4 flex items-center gap-2 rounded-lg border border-success/20 bg-success-dim px-3 py-3 text-sm text-success"
          >
            <Check className="size-4" />
            {invited} judge{invited === 1 ? "" : "s"} invited
          </div>
        )}
        <div id="invite-error">
          <ActionFailure error={error} />
        </div>
      </form>
    </ActionCard>
  );
}

export function AssignmentPanel() {
  const notify = useContext(ToastContext);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssignmentRunResponse | null>(null);

  async function run() {
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await api.runAssignment();
      setResult(data);
      setStatus("idle");
      notify("Judge assignment completed.");
    } catch (err) {
      setStatus("error");
      setError(actionError(err, "We couldn’t assign projects to judges."));
    }
  }

  return (
    <ActionCard
      icon={GitBranch}
      label="02 / DISTRIBUTE"
      title="Run assignment"
      description="Distribute projects across your judges with disjoint review batches. Each project gets three independent reviews."
    >
      <div className="mb-6 rounded-xl border border-dashed bg-bg/50 p-4">
        <p className="text-xs text-text-muted">Review coverage</p>
        <p className="mt-2 font-mono text-2xl tabular-nums">
          3{" "}
          <span className="font-sans text-sm text-text-secondary">
            reviews / project
          </span>
        </p>
        <p className="mt-3 text-xs leading-relaxed text-text-muted">
          Assignments use a repeatable seed for a consistent review plan.
        </p>
      </div>
      <Button
        variant="outline"
        onClick={run}
        disabled={status === "loading"}
        className="mt-auto w-full"
        aria-busy={status === "loading"}
      >
        {status === "loading" ? (
          <BusyIcon />
        ) : (
          <ArrowRight className="size-4" />
        )}
        {status === "loading" ? "Assigning projects…" : "Run assignment"}
      </Button>
      {result && (
        <div
          role="status"
          className="mt-4 rounded-xl border border-success/20 bg-success-dim p-4"
        >
          <p className="flex items-center gap-2 text-sm font-medium text-success">
            <CheckCircle2 className="size-4" />
            Assignment complete
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-text-secondary">Assignments</dt>
              <dd className="mt-1 font-mono text-lg">{result.n_assignments}</dd>
            </div>
            <div>
              <dt className="text-text-secondary">Seed</dt>
              <dd className="mt-1 font-mono text-lg">{result.seed_used}</dd>
            </div>
          </dl>
          {result.judges_with_zero_projects.length > 0 && (
            <p className="mt-3 text-xs leading-relaxed text-accent-2">
              {result.judges_with_zero_projects.length} judge
              {result.judges_with_zero_projects.length === 1
                ? " has"
                : "s have"}{" "}
              no assigned projects. Check review coverage.
            </p>
          )}
        </div>
      )}
      <ActionFailure error={error} />
    </ActionCard>
  );
}

export function NormalizationPanel() {
  const notify = useContext(ToastContext);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NormalizeResponse | null>(null);

  async function run() {
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await api.runNormalization();
      setResult(data);
      setStatus("idle");
      notify("Score normalization completed.");
    } catch (err) {
      setStatus("error");
      setError(actionError(err, "We couldn’t normalize the scores."));
    }
  }

  return (
    <ActionCard
      icon={Scale}
      label="03 / CALIBRATE"
      title="Run normalization"
      description="Account for judge scoring differences across the event. Review the score distribution before sharing your results."
    >
      <div className="mb-6 rounded-xl border border-dashed bg-bg/50 p-4">
        <p className="text-xs text-text-muted">A fairer final score</p>
        <div className="mt-3 flex items-center gap-2 text-accent">
          <span className="h-7 w-3 rounded-sm bg-accent/25" />
          <span className="h-11 w-3 rounded-sm bg-accent/45" />
          <span className="h-6 w-3 rounded-sm bg-accent/30" />
          <ArrowRight className="mx-1 size-4" />
          <span className="h-8 w-3 rounded-sm bg-accent/60" />
          <span className="h-9 w-3 rounded-sm bg-accent" />
          <span className="h-8 w-3 rounded-sm bg-accent/60" />
          <span className="sr-only">Normalize variation between judges</span>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-text-muted">
          Calibrates scores using the additive judge-bias model.
        </p>
      </div>
      <Button
        variant="outline"
        onClick={run}
        disabled={status === "loading"}
        className="mt-auto w-full"
        aria-busy={status === "loading"}
      >
        {status === "loading" ? (
          <BusyIcon />
        ) : (
          <ArrowRight className="size-4" />
        )}
        {status === "loading" ? "Calibrating scores…" : "Run normalization"}
      </Button>
      {result && (
        <div
          role="status"
          className="mt-4 rounded-xl border border-success/20 bg-success-dim p-4"
        >
          <p className="flex items-center gap-2 text-sm font-medium text-success">
            <CheckCircle2 className="size-4" />
            Scores calibrated
          </p>
          <p className="mt-3 text-xs text-text-secondary">
            Score deviation · σ
          </p>
          <p className="mt-1 flex items-center gap-3 font-mono text-xl tabular-nums">
            {result.raw_sigma.toFixed(3)}
            <ArrowRight className="size-4 text-text-muted" />
            {result.normalized_sigma.toFixed(3)}
          </p>
          <p className="mt-3 text-xs leading-relaxed text-text-secondary">
            {result.n_projects} projects · {result.n_judges} judges ·{" "}
            {result.n_reviews} reviews
          </p>
          {!result.is_connected && (
            <p className="mt-3 text-xs leading-relaxed text-accent-2">
              Review groups are disconnected. Interpret cross-group scores with
              care.
            </p>
          )}
        </div>
      )}
      <ActionFailure error={error} />
    </ActionCard>
  );
}
