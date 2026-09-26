import { cookies } from "next/headers";
import { api } from "@/lib/api/client";
import { AssignmentPanel, BulkInvitePanel, NormalizationPanel } from "./actions";
import styles from "./organizer.module.css";

export default async function OrganizerPage() {
  const cookieHeader = (await cookies()).toString();
  const [event, memberships] = await Promise.all([
    api.eventDetail(undefined, cookieHeader),
    api.memberships(undefined, cookieHeader),
  ]);

  const roleCounts = memberships.reduce<Record<string, number>>((acc, m) => {
    acc[m.role] = (acc[m.role] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <h1>{event.name}</h1>
      <p className={styles.lede}>{event.description}</p>

      <div className={styles.overview}>
        <div>
          <span className={styles.label}>State</span>
          <span>{event.state}</span>
        </div>
        <div>
          <span className={styles.label}>Submissions close</span>
          <span>{new Date(event.submissions_close_at).toLocaleString()}</span>
        </div>
        <div>
          <span className={styles.label}>Judging window</span>
          <span>
            {new Date(event.judging_open_at).toLocaleString()} –{" "}
            {new Date(event.judging_close_at).toLocaleString()}
          </span>
        </div>
        <div>
          <span className={styles.label}>Voting mode</span>
          <span>{event.voting_mode}</span>
        </div>
      </div>

      <h2 className={styles.sectionTitle}>Membership</h2>
      <div className={styles.roleCounts}>
        {Object.entries(roleCounts).map(([role, count]) => (
          <span key={role} className={styles.roleChip}>
            {count} {role}
            {count === 1 ? "" : "s"}
          </span>
        ))}
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
          </tr>
        </thead>
        <tbody>
          {memberships.map((m) => (
            <tr key={m.id}>
              <td>{m.user_name}</td>
              <td>{m.user_email}</td>
              <td>{m.role}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className={styles.sectionTitle}>Actions</h2>
      <div className={styles.actions}>
        <BulkInvitePanel />
        <AssignmentPanel />
        <NormalizationPanel />
        <section className={styles.exportPanel}>
          <h2>Export</h2>
          <p className={styles.hint}>
            Download the current scores as CSV for offline review.
          </p>
          <a className={styles.exportButton} href={api.csvExportUrl()} download>
            Export scores (CSV)
          </a>
        </section>
      </div>
    </div>
  );
}
