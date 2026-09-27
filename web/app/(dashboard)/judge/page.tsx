import { cookies } from "next/headers";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default async function JudgePage() {
  const cookieHeader = (await cookies()).toString();
  let batch;
  try {
    batch = await api.meBatch(undefined, cookieHeader);
  } catch (err) {
    // The layout already guarantees a signed-in session — a 403 here
    // means this account just doesn't hold a judge assignment.
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

  // A judge can hold assignments across more than one batch (e.g. the
  // organizer re-runs assignment), and meBatch() doesn't dedupe across
  // them — collapse by project id so the same project never renders twice.
  const projects = Array.from(
    new Map(batch.projects.map((p) => [p.id, p])).values(),
  );

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Your batch</h1>
      <p className="mt-1 text-muted-foreground">
        {batch.progress.scored} of {batch.progress.total} reviewed
      </p>
      {projects.length === 0 ? (
        <Alert className="mt-6">
          <AlertDescription>No submissions assigned to you yet.</AlertDescription>
        </Alert>
      ) : (
        <ul className="mt-6 flex flex-col gap-2">
          {projects.map((project) => (
            <li key={project.id}>
              <Card className="flex flex-row items-center justify-between gap-3 p-4">
                <Link
                  href={`/judge/${project.id}`}
                  className="flex flex-1 flex-col gap-1"
                >
                  <span className="font-semibold">{project.name}</span>
                  <span className="text-sm text-muted-foreground">{project.tagline}</span>
                </Link>
                <Badge variant={project.reviewed ? "default" : "secondary"}>
                  {project.reviewed ? "Reviewed" : "Pending"}
                </Badge>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
