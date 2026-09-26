import Link from "next/link";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.hero}>
      <h1>Dogfood Portal</h1>
      <p className={styles.lede}>
        Submit a project, judge a batch, or browse what shipped.
      </p>
      <div className={styles.links}>
        <Link className={styles.primary} href="/gallery">
          View gallery
        </Link>
        <Link className={styles.secondary} href="/submit">
          Submit a project
        </Link>
      </div>
    </div>
  );
}
