import Link from "next/link";
import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import styles from "./gallery.module.css";

export default async function GalleryPage() {
  const data = await api.gallery();

  return (
    <div>
      <h1>Gallery</h1>
      {data.items.length === 0 ? (
        <EmptyState>No projects have been submitted yet.</EmptyState>
      ) : (
        <ul className={styles.grid}>
          {data.items.map((item) => (
            <li key={item.id} className={styles.card}>
              {/* Wrap the entire card in a Link so the whole tile is
                  clickable, not just the title. */}
              <Link href={`/gallery/${item.id}`} className={styles.cardLink}>
                <h2>{item.name}</h2>
                <p className={styles.tagline}>{item.tagline}</p>
                <span className={styles.track}>{item.track_slug}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
