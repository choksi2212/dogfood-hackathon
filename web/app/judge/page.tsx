import { cookies } from "next/headers";
import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import styles from "./judge.module.css";

export default async function JudgePage() {
  const cookieHeader = (await cookies()).toString();
  const data = await api.judgeScores(cookieHeader);

  return (
    <div>
      <h1>Your scores</h1>
      {data.scores.length === 0 ? (
        <EmptyState>No submissions assigned to you yet.</EmptyState>
      ) : (
        <ul className={styles.list}>
          {data.scores.map((score, i) => (
            <li
              key={`${score.project_id}-${score.criterion_id}-${i}`}
              className={styles.row}
            >
              <span className={styles.name}>
                Project {score.project_id.slice(0, 8)}
              </span>
              <span className={styles.criterion}>
                Criterion {score.criterion_id.slice(0, 8)}
              </span>
              <span className={styles.score}>{score.value}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
