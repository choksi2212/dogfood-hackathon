import styles from "./StateMessage.module.css";

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className={styles.box}>{children}</div>;
}

export function ErrorState({ children }: { children: React.ReactNode }) {
  return <div className={`${styles.box} ${styles.error}`}>{children}</div>;
}

export function LoadingState({ children }: { children: React.ReactNode }) {
  return <div className={styles.box}>{children}</div>;
}
