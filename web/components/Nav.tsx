"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const PUBLIC_LINKS = [
  { href: "/gallery", label: "Gallery" },
  { href: "/submit", label: "Submit" },
  { href: "/vote", label: "Vote" },
  { href: "/pairwise", label: "Pairwise" },
  { href: "/certificates", label: "Certificates" },
];

const TOOL_LINKS = [
  { href: "/judge", label: "Judge" },
  { href: "/organizer", label: "Organizer" },
  { href: "/widget", label: "Widget" },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav}>
      <div className={styles.group}>
        {PUBLIC_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={styles.link}
            data-active={isActive(pathname, link.href) || undefined}
          >
            {link.label}
          </Link>
        ))}
      </div>
      <div className={styles.divider} aria-hidden="true" />
      <div className={styles.group}>
        {TOOL_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={styles.link}
            data-active={isActive(pathname, link.href) || undefined}
          >
            {link.label}
          </Link>
        ))}
      </div>
      <Link href="/login" className={styles.login}>
        Log in
      </Link>
    </nav>
  );
}
