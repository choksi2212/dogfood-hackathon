import { cookies } from "next/headers";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/Button";
import styles from "./results.module.css";

export default async function VotingResultsPage() {
  const cookieHeader = (await cookies()).toString();
  const [votes, audit] = await Promise.all([
    api.voteResults(undefined, cookieHeader),
    api.auditLog(undefined, 100, cookieHeader),
  ]);

  const topVotes = votes.results.length
    ? Math.max(...votes.results.map((r) => r.total_votes))
    : 0;

  return (
    <div>
      <PageHeader
        title="Voting results & audit log"
        actions={
          <Link href="/organizer">
            <Button variant="secondary">Back to dashboard</Button>
          </Link>
        }
      />

      <section>
        <h2 className={styles.sectionTitle}>Results</h2>
        <p className={styles.hint}>
          Mode: {votes.voting_mode} ·{" "}
          {votes.results_visible
            ? "visible (results window is open)"
            : "hidden from participants until the results window opens — you can see it as organizer"}
        </p>
        {votes.results.length === 0 ? (
          <EmptyState>No submitted projects yet.</EmptyState>
        ) : (
          <ol className={styles.resultsList}>
            {votes.results.map((row, i) => (
              <li key={row.project_id} className={styles.resultRow}>
                <span className={styles.rank}>#{i + 1}</span>
                <span className={styles.projectName}>{row.project_name}</span>
                <span className={styles.barTrack}>
                  <span
                    className={styles.bar}
                    style={{
                      width: `${topVotes ? (row.total_votes / topVotes) * 100 : 0}%`,
                    }}
                  />
                </span>
                <span className={styles.count}>
                  {row.total_votes} vote{row.total_votes === 1 ? "" : "s"}
                  {row.vote_count !== row.total_votes && ` (${row.vote_count} ballots)`}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section>
        <h2 className={styles.sectionTitle}>Audit log</h2>
        <p className={styles.hint}>Most recent 100 events, newest first.</p>
        {audit.entries.length === 0 ? (
          <EmptyState>No audit events recorded yet.</EmptyState>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Target</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {audit.entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{new Date(entry.created_at).toLocaleString()}</td>
                  <td>{entry.actor_email ?? "anonymous"}</td>
                  <td>{entry.action}</td>
                  <td>
                    {entry.target_type}
                    {entry.target_id ? ` #${entry.target_id.slice(0, 8)}` : ""}
                  </td>
                  <td>
                    <span className={styles[`result_${entry.result}`]}>
                      {entry.result}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
