import { cookies } from "next/headers";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { AssignmentPanel, BulkInvitePanel, NormalizationPanel } from "./actions";
import { EmptyState, ErrorState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
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
            <Link href="/login">
              <Button variant="primary">Sign in</Button>
            </Link>
          </EmptyState>
        );
      }
      if (err.status === 403) {
        return (
          <EmptyState>
            <h2>Organizer role required</h2>
            <p>
              You&apos;re signed in, but this account isn&apos;t listed as an
              organizer for this event. Ask the event owner to add you.
            </p>
          </EmptyState>
        );
      }
    }
    return (
      <ErrorState>
        Couldn&apos;t load the dashboard:{" "}
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
      <PageHeader
        title={event.name}
        description={event.description}
        actions={
          <Link href="/organizer/results">
            <Button variant="secondary">Voting results &amp; audit log →</Button>
          </Link>
        }
      />

      <Card className={styles.overview}>
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
      </Card>

      <h2 className={styles.sectionTitle}>Membership</h2>
      <div className={styles.roleCounts}>
        {Object.entries(roleCounts).map(([role, count]) => (
          <Badge key={role} tone="neutral">
            {count} {role}
            {count === 1 ? "" : "s"}
          </Badge>
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
        <Card className={styles.exportPanel}>
          <h2>Export</h2>
          <p className={styles.hint}>
            Download the current scores as CSV for offline review.
          </p>
          <a href={api.csvExportUrl()} download>
            <Button variant="primary" className={styles.exportButton}>
              Export scores (CSV)
            </Button>
          </a>
        </Card>
      </div>
    </div>
  );
}
