import { cookies } from "next/headers";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import styles from "./ranking.module.css";

export default async function PairwiseRankingPage() {
  const cookieHeader = (await cookies()).toString();
  const data = await api.pairwiseRanking(undefined, cookieHeader);

  return (
    <div>
      <div className={styles.header}>
        <h1>Pairwise ranking</h1>
        <Link href="/pairwise">Back to compare</Link>
      </div>
      <p className={styles.meta}>
        {data.n_ballots} ballots · {data.iterations} iterations ·{" "}
        {data.converged ? "converged" : "not yet converged"}
      </p>
      {data.ranking.length === 0 ? (
        <EmptyState>No ballots cast yet.</EmptyState>
      ) : (
        <ol className={styles.list}>
          {data.ranking.map((entry) => (
            <li key={entry.project_id} className={styles.row}>
              <span className={styles.rank}>#{entry.rank}</span>
              <span className={styles.project}>
                Project {entry.project_id.slice(0, 8)}
              </span>
              <span className={styles.record}>
                {entry.wins}W / {entry.losses}L / {entry.ties}T
              </span>
              <span className={styles.theta}>θ {entry.theta.toFixed(3)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
