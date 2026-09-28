"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { Brand } from "@/components/brand";
import { Button, buttonVariants } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/cn";

const links = [
  { href: "/gallery", label: "Gallery" },
  { href: "/certificates", label: "Certificates" },
  { href: "/widget", label: "Widget" },
  { href: "/#how-it-works", label: "How it works" },
];
export function SiteHeader({ minimal = false }: { minimal?: boolean }) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 50);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);
  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 border-b bg-bg/80 backdrop-blur-md transition-colors",
        scrolled || open || minimal ? "border-border/80" : "border-transparent",
      )}
    >
      <div className="container-shell flex h-16 items-center justify-between gap-4">
        <Brand />
        {!minimal && (
          <nav
            aria-label="Main navigation"
            className="hidden items-center gap-7 md:flex"
          >
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-link text-sm text-text-secondary hover:text-text-primary"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="/login"
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "gap-2",
            )}
          >
            Log in
            <ArrowUpRight className="size-3.5" />
          </Link>
          {!minimal && (
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label={open ? "Close navigation" : "Open navigation"}
              aria-expanded={open}
              aria-controls="mobile-nav"
              onClick={() => setOpen(!open)}
            >
              {open ? <X /> : <Menu />}
            </Button>
          )}
        </div>
      </div>
      {open && !minimal && (
        <nav
          id="mobile-nav"
          aria-label="Mobile navigation"
          className="container-shell flex flex-col gap-1 border-t py-3 md:hidden"
        >
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-3 text-sm hover:bg-accent-dim"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
