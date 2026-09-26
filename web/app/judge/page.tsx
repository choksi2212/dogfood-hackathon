import { cookies } from "next/headers";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import styles from "./judge.module.css";

export default async function JudgePage() {
  const cookieHeader = (await cookies()).toString();
  const batch = await api.meBatch(undefined, cookieHeader);

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
