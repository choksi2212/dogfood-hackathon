import { cookies } from "next/headers";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { EmptyState } from "@/components/StateMessage";
import { ExportCsvButton } from "./ExportCsvButton";
import styles from "./ranking.module.css";

export default async function PairwiseRankingPage() {
  const cookieHeader = (await cookies()).toString();
  const [data, gallery] = await Promise.all([
    api.pairwiseRanking(undefined, cookieHeader),
    // Ranking only has project_id (the fit doesn't carry names) — join
    // against the public gallery to show real project names instead of
    // raw UUIDs, same fix as the judge console and organizer dashboard.
    api.gallery(),
  ]);

  const namesById = new Map(gallery.items.map((p) => [p.id, p.name]));
  const rows = data.ranking.map((entry) => ({
    ...entry,
    project_name: namesById.get(entry.project_id) ?? `Project ${entry.project_id.slice(0, 8)}`,
  }));

  return (
    <div>
      <div className={styles.header}>
        <h1>Pairwise ranking</h1>
        <div className={styles.headerActions}>
          {rows.length > 0 && (
            <ExportCsvButton rows={rows} eventSlug={EVENT_SLUG} />
          )}
          <Link href="/pairwise">Back to compare</Link>
        </div>
      </div>
      <p className={styles.meta}>
        {data.n_ballots} ballots · {data.iterations} iterations ·{" "}
        {data.converged ? "converged" : "not yet converged"}
      </p>
      {rows.length === 0 ? (
        <EmptyState>No ballots cast yet.</EmptyState>
      ) : (
        <ol className={styles.list}>
          {rows.map((entry) => (
            <li key={entry.project_id} className={styles.row}>
              <span className={styles.rank}>#{entry.rank}</span>
              <span className={styles.project}>{entry.project_name}</span>
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
