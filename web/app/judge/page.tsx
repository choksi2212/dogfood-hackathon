import { cookies } from "next/headers";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState } from "@/components/StateMessage";
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
              Only assigned judges can see the projects they're scoring.
            </p>
            <Link href="/login" className={styles.signinLink}>
              Sign in
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
              You're signed in, but you don't have one for this event.
            </p>
          </EmptyState>
        );
      }
      return (
        <ErrorState>
          Couldn't load your batch: {err.message}
        </ErrorState>
      );
    }
    return <ErrorState>Couldn't load your batch.</ErrorState>;
  }

  return (
    <div>
      <h1>Your batch</h1>
      <p className={styles.progress}>
        {batch.progress.scored} of {batch.progress.total} reviewed
      </p>
      {batch.projects.length === 0 ? (
        <EmptyState>No submissions assigned to you yet.</EmptyState>
      ) : (
        <ul className={styles.list}>
          {batch.projects.map((project) => (
            <li key={project.id} className={styles.row}>
              <Link href={`/judge/${project.id}`} className={styles.link}>
                <span className={styles.name}>{project.name}</span>
                <span className={styles.tagline}>{project.tagline}</span>
              </Link>
              <span
                className={
                  project.reviewed ? styles.badgeDone : styles.badgePending
                }
              >
                {project.reviewed ? "Reviewed" : "Pending"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
