import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Nav } from "@/components/Nav";
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
            <Link href="/gallery" className={styles.brand}>
              Dogfood Portal
            </Link>
            <Nav />
          </header>
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
