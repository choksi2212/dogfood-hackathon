import { cookies } from "next/headers";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import styles from "./judge.module.css";

export default async function JudgePage() {
  const cookieHeader = (await cookies()).toString();
  let batch;
  try {
    batch = await api.meBatch(undefined, cookieHeader);
  } catch (err) {
    // Three distinct failure modes, each with its own message — the
    // raw 403 from the backend reads as a system bug to anyone who
    // doesn't know what ``forbidden_role`` means.
    if (err instanceof ApiError) {
      if (err.status === 401) {
        return (
          <EmptyState>
            <h2>Sign in to see your batch</h2>
            <p>
              Only assigned judges can see the projects they&apos;re scoring.
            </p>
            <Link href="/login">
              <Button variant="primary">Sign in</Button>
            </Link>
          </EmptyState>
        );
      }
      if (err.status === 403) {
        return (
          <EmptyState>
            <h2>No batch assigned</h2>
            <p>
              Judging assignments are issued per-judge by the organizer.
              You&apos;re signed in, but you don&apos;t have one for this event.
            </p>
          </EmptyState>
        );
      }
      return (
        <ErrorState>
          Couldn&apos;t load your batch: {err.message}
        </ErrorState>
      );
    }
    return <ErrorState>Couldn&apos;t load your batch.</ErrorState>;
  }

  // A judge can hold assignments across more than one batch (e.g. the
  // organizer re-runs assignment), and meBatch() doesn't dedupe across
  // them — collapse by project id so the same project never renders twice.
  const projects = Array.from(
    new Map(batch.projects.map((p) => [p.id, p])).values(),
  );

  return (
    <div>
      <PageHeader
        title="Your batch"
        description={`${batch.progress.scored} of ${batch.progress.total} reviewed`}
      />
      {projects.length === 0 ? (
        <EmptyState>No submissions assigned to you yet.</EmptyState>
      ) : (
        <ul className={styles.list}>
          {projects.map((project) => (
            <li key={project.id}>
              <Card className={styles.row}>
                <Link href={`/judge/${project.id}`} className={styles.link}>
                  <span className={styles.name}>{project.name}</span>
                  <span className={styles.tagline}>{project.tagline}</span>
                </Link>
                <Badge tone={project.reviewed ? "success" : "neutral"}>
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
