import { api } from "@/lib/api/client";
import styles from "./organizer.module.css";

export default function OrganizerPage() {
  return (
    <div>
      <h1>Organizer</h1>
      <p className={styles.lede}>
        Export the current scores as CSV for offline review.
      </p>
      <a className={styles.button} href={api.csvExportUrl()} download>
        Export scores (CSV)
      </a>
    </div>
  );
}
