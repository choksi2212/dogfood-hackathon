import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import styles from "./judge.module.css";

export default async function JudgePage() {
  const data = await api.judgeScores();

  return (
    <div>
      <h1>Your batch</h1>
      {data.scores.length === 0 ? (
        <EmptyState>No submissions assigned to you yet.</EmptyState>
      ) : (
        <ul className={styles.list}>
          {data.scores.map((score, i) => (
            <li key={`${score.submission_id}-${i}`} className={styles.row}>
              <span className={styles.name}>{score.submission_name}</span>
              <span className={styles.criterion}>{score.criterion}</span>
              <span className={styles.score}>
                {score.score}/{score.max_score}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
