import Link from "next/link";
import { GitBranch, ArrowUpRight } from "lucide-react";
import { Brand } from "@/components/brand";

const groups = [
  {
    title: "Product",
    links: [
      ["Gallery", "/gallery"],
      ["Submit a project", "/submit"],
      ["Judge workspace", "/judge"],
    ],
  },
  {
    title: "Resources",
    links: [
      ["Certificates", "/certificates"],
      ["Embed widget", "/widget"],
      ["How it works", "/#how-it-works"],
    ],
  },
  {
    title: "The event",
    links: [
      ["About Hack Hamster", "/#about"],
      ["Judging principles", "/#judging"],
      ["Get started", "/register"],
    ],
  },
];
export function SiteFooter() {
  return (
    <footer className="border-t bg-bg-elevated">
      <div className="container-shell py-14">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Brand />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-text-secondary">
              For the ideas that keep you up.
              <br />
              And the people who ship them.
            </p>
            <span className="mt-5 inline-flex items-center gap-2 font-mono text-xs text-text-muted">
              <span className="size-1.5 rounded-full bg-success" />
              HACK HAMSTER 2026
            </span>
          </div>
          {groups.map((group) => (
            <div key={group.title}>
              <h2 className="mb-5 font-mono text-xs uppercase tracking-caps text-text-muted">
                {group.title}
              </h2>
              <ul className="space-y-3">
                {group.links.map(([label, href]) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="text-link text-sm text-text-secondary hover:text-text-primary"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t pt-6 text-xs text-text-muted">
          <span>© 2026 Hack Hamster Hackathon. Built for builders.</span>
          <a
            href="https://github.com/choksi2212/dogfood-hackathon"
            target="_blank"
            rel="noreferrer"
            className="text-link"
          >
            <GitBranch className="size-4" />
            GitHub
            <ArrowUpRight className="size-3" />
          </a>
        </div>
      </div>
    </footer>
  );
}
