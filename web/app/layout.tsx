import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: "Dogfood Portal",
  description: "Hackathon submission and judging portal.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className={styles.shell}>
          <header className={styles.header}>
            <span className={styles.brand}>Dogfood Portal</span>
            <nav className={styles.nav}>
              <Link href="/gallery">Gallery</Link>
              <Link href="/submit">Submit</Link>
              <Link href="/vote">Vote</Link>
              <Link href="/judge">Judge</Link>
              <Link href="/pairwise">Pairwise</Link>
              <Link href="/organizer">Organizer</Link>
              <Link href="/login">Log in</Link>
            </nav>
          </header>
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
