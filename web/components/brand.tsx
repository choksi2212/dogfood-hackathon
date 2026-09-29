import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/cn";

/**
 * Brand mark for Hack Hamster.
 *
 * - `compact` shows only the symbol (for tight spaces — sidebar collapsed,
 *   mobile nav, etc.).
 * - The lockup picks the dark or light horizontal variant based on the
 *   resolved theme; the symbol picks dark or light mark accordingly.
 *
 * Uses the SVG files under /public/hack-hamster-logo/. Mark = `#E2454A` (red)
 * on both dark and light surfaces; the lockup pairs it with `#F5F5F5`
 * (offwhite) or `#303030` (charcoal) — the Hack Hamster brand palette.
 */
export function Brand({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  return (
    <Link
      href="/"
      aria-label="Hack Hamster home"
      className={cn(
        "inline-flex items-center gap-2.5 transition-opacity hover:opacity-80",
        className,
      )}
    >
      {compact ? (
        <span className="inline-flex">
          {/* light=light-bg variant, dark=dark-bg variant (both use the red mark). */}
          <LogoMark />
        </span>
      ) : (
        <span className="inline-flex">
          <LogoLockup />
        </span>
      )}
    </Link>
  );
}

function LogoLockup() {
  // Render both variants stacked — CSS shows the one matching the active
  // theme (next-themes toggles `.dark` on <html>).
  return (
    <>
      <Image
        src="/hack-hamster-logo/01-horizontal-dark.svg"
        alt="Hack Hamster"
        width={120}
        height={30}
        className="hidden h-7 w-auto dark:block"
        priority
      />
      <Image
        src="/hack-hamster-logo/02-horizontal-light.svg"
        alt="Hack Hamster"
        width={120}
        height={30}
        className="block h-7 w-auto dark:hidden"
        priority
      />
    </>
  );
}

function LogoMark() {
  return (
    <>
      <Image
        src="/hack-hamster-logo/04-mark-dark.svg"
        alt=""
        width={36}
        height={36}
        className="hidden h-9 w-9 dark:block"
        aria-hidden
      />
      <Image
        src="/hack-hamster-logo/05-mark-light.svg"
        alt=""
        width={36}
        height={36}
        className="block h-9 w-9 dark:hidden"
        aria-hidden
      />
    </>
  );
}
