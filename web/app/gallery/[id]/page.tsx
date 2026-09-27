import Link from "next/link";
import { notFound } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import styles from "./detail.module.css";

export default async function SubmissionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let submission;
  try {
    submission = await api.submission(id);
  } catch (err) {
    // 404 → render the framework not-found so the navbar/back button
    // still works. Anything else → render an error card with the actual
    // message so the user knows what broke (e.g. backend down).
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    return (
      <ErrorState>
        {err instanceof Error ? err.message : "Couldn't load this submission."}
      </ErrorState>
    );
  }

  const submitted = submission.submitted_at
    ? new Date(submission.submitted_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "—";

  return (
    <article className={styles.article}>
      <Link href="/gallery" className={styles.back}>
        ← Back to gallery
      </Link>

      <header className={styles.header}>
        <div className={styles.eyebrow}>{submission.track_slug}</div>
        <h1 className={styles.title}>{submission.name}</h1>
        {submission.tagline && (
          <p className={styles.tagline}>{submission.tagline}</p>
        )}
        <div className={styles.meta}>
          <span>{submission.team_name}</span>
          <span aria-hidden="true">·</span>
          <span>Submitted {submitted}</span>
          <span aria-hidden="true">·</span>
          <span className={styles.status}>{submission.status}</span>
        </div>
      </header>

      {submission.description && (
        <section className={styles.section}>
          <h2 className={styles.h2}>About the project</h2>
          <p className={styles.description}>{submission.description}</p>
        </section>
      )}

      {(submission.repo_url ||
        submission.live_url ||
        submission.demo_video_url) && (
        <section className={styles.section}>
          <h2 className={styles.h2}>Links</h2>
          <ul className={styles.links}>
            {submission.demo_video_url && (
              <li>
                <a
                  href={submission.demo_video_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Demo video ↗
                </a>
              </li>
            )}
            {submission.repo_url && (
              <li>
                <a
                  href={submission.repo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Source ↗
                </a>
              </li>
            )}
            {submission.live_url && (
              <li>
                <a
                  href={submission.live_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Live site ↗
                </a>
              </li>
            )}
          </ul>
        </section>
      )}

      <footer className={styles.footer}>
        <Link href="/gallery" className={styles.footerLink}>
          ← Back to gallery
        </Link>
      </footer>
    </article>
  );
}
