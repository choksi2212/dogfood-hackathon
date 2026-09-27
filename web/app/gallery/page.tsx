import Link from "next/link";
import { api } from "@/lib/api/client";
import { EmptyState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import styles from "./gallery.module.css";

export default async function GalleryPage() {
  const data = await api.gallery();

  return (
    <div>
      <PageHeader
        title="Gallery"
        description="Every project submitted to this event."
      />
      {data.items.length === 0 ? (
        <EmptyState>No projects have been submitted yet.</EmptyState>
      ) : (
        <ul className={styles.grid}>
          {data.items.map((item) => (
            <li key={item.id}>
              {/* Wrap the entire card in a Link so the whole tile is
                  clickable, not just the title. */}
              <Link href={`/gallery/${item.id}`} className={styles.cardLink}>
                <Card interactive className={styles.card}>
                  <h2 className={styles.name}>{item.name}</h2>
                  <p className={styles.tagline}>{item.tagline}</p>
                  <Badge tone="accent">{item.track_slug}</Badge>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
