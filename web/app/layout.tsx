import type { Metadata } from "next";
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
              <a href="/gallery">Gallery</a>
              <a href="/submit">Submit</a>
              <a href="/judge">Judge</a>
              <a href="/organizer">Organizer</a>
              <a href="/login">Log in</a>
            </nav>
          </header>
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
