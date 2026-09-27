import { cookies } from "next/headers";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { AssignmentPanel, BulkInvitePanel, NormalizationPanel } from "./actions";
import { EmptyState, ErrorState } from "@/components/StateMessage";
import styles from "./organizer.module.css";

export default async function OrganizerPage() {
  const cookieHeader = (await cookies()).toString();

  let event;
  let memberships;
  try {
    [event, memberships] = await Promise.all([
      api.eventDetail(undefined, cookieHeader),
      api.memberships(undefined, cookieHeader),
    ]);
  } catch (err) {
    // Same three-state treatment as /judge — anon → sign in, 403 →
    // "you're signed in but not an organizer", anything else →
    // generic error with the real message.
    if (err instanceof ApiError) {
      if (err.status === 401) {
        return (
          <EmptyState>
            <h2>Sign in to access the dashboard</h2>
            <p>Only organizers can see this page.</p>
            <Link href="/login" className={styles.signinLink}>
              Sign in
            </Link>
          </EmptyState>
        );
      }
      if (err.status === 403) {
        return (
          <EmptyState>
            <h2>Organizer role required</h2>
            <p>
              You're signed in, but this account isn't listed as an
              organizer for this event. Ask the event owner to add you.
            </p>
          </EmptyState>
        );
      }
    }
    return (
      <ErrorState>
        Couldn't load the dashboard:{" "}
        {err instanceof Error ? err.message : "Unknown error."}
      </ErrorState>
    );
  }

  const roleCounts = memberships.reduce<Record<string, number>>((acc, m) => {
    acc[m.role] = (acc[m.role] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <div className={styles.titleRow}>
        <div>
          <h1>{event.name}</h1>
          <p className={styles.lede}>{event.description}</p>
        </div>
        <Link href="/organizer/results" className={styles.resultsLink}>
          Voting results &amp; audit log →
        </Link>
      </div>

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
