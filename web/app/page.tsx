import Link from "next/link";
import { Button } from "@/components/Button";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.hero}>
      <span className={styles.eyebrow}>Hackathon judging portal</span>
      <h1 className={styles.title}>Dogfood Portal</h1>
      <p className={styles.lede}>
        Submit a project, judge a batch, cast a vote, or browse what shipped —
        all in one place.
      </p>
      <div className={styles.links}>
        <Link href="/gallery">
          <Button variant="primary">View gallery</Button>
        </Link>
        <Link href="/submit">
          <Button variant="secondary">Submit a project</Button>
        </Link>
      </div>
    </div>
  );
}
