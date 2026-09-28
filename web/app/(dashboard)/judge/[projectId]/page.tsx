import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScoreForm } from "./ScoreForm";

export default async function JudgeScorePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const cookieHeader = (await cookies()).toString();

  let batch;
  let event;
  let judgeScores;
  try {
    [batch, event, judgeScores] = await Promise.all([
      api.meBatch(undefined, cookieHeader),
      api.eventDetail(undefined, cookieHeader),
      // Pre-fill the form with whatever this judge already saved —
      // without this, revisiting an already-scored project silently
      // resets every slider to 0, and re-submitting overwrites the
      // real scores with zeros.
      api.judgeScores(cookieHeader),
    ]);
  } catch (err) {
    // Same 403 shape as /judge itself — this account isn't a judge, or
    // is a judge with no batch at all, for this event.
    if (err instanceof ApiError && err.status === 403) {
      return (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertTitle>No batch assigned</AlertTitle>
          <AlertDescription>
            Judging assignments are issued per-judge by the organizer. You&apos;re
            signed in, but you don&apos;t have one for this event.
          </AlertDescription>
        </Alert>
      );
    }
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" />
        <AlertDescription>
          Couldn&apos;t load your batch: {err instanceof Error ? err.message : "unknown error"}
        </AlertDescription>
      </Alert>
    );
  }

  const project = batch.projects.find((p) => p.id === projectId);
  if (!project) {
    notFound();
  }

  const criteria = event.rubric?.criteria ?? [];
  const initialValues = Object.fromEntries(
    judgeScores.scores
      .filter((s) => s.project_id === project.id)
      .map((s) => [s.criterion_id, s.value]),
  );

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
      <p className="mt-1 text-muted-foreground">{project.tagline}</p>
      <div className="mt-6">
        <ScoreForm
          projectId={project.id}
          criteria={criteria}
          initialValues={initialValues}
          initialSubmittedAt={project.submitted_at}
        />
      </div>
    </div>
  );
}
