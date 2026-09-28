import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  CalendarDays,
  Code2,
  ExternalLink,
  Globe2,
  Layers3,
  Play,
  UsersRound,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { ClientDate } from "@/components/client-date";
import { LoadError } from "@/components/portal-ui";
import { cn } from "@/lib/cn";

export default async function SubmissionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let submission;
  try {
    submission = await api.submission(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    return (
      <div className="py-8">
        <LoadError
          title="This project couldn’t be loaded"
          description="Please try again in a moment."
          href={`/gallery/${encodeURIComponent(id)}`}
        />
      </div>
    );
  }
  const hasDistinctTagline =
    submission.tagline && submission.tagline !== submission.name;
  const links = [
    {
      url: submission.live_url,
      title: "Explore the live project",
      hint: "Try it for yourself",
      icon: Globe2,
    },
    {
      url: submission.demo_video_url,
      title: "Watch the demo",
      hint: "See the idea in action",
      icon: Play,
    },
    {
      url: submission.repo_url,
      title: "View source code",
      hint: "Go behind the build",
      icon: Code2,
    },
  ].filter((link) => {
    try {
      return ["http:", "https:"].includes(new URL(link.url).protocol);
    } catch {
      return false;
    }
  });

  return (
    <article>
      <Link
        href="/gallery"
        className="inline-flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-accent"
      >
        <ArrowLeft className="size-4" />
        Back to gallery
      </Link>
      <header className="relative mt-7 overflow-hidden rounded-3xl border border-border bg-bg-elevated px-7 py-10 sm:px-10 sm:py-14 lg:px-12">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-12 bottom-0 hidden font-mono text-[180px] leading-none font-medium text-accent/[.04] lg:block"
        >
          &lt;/&gt;
        </div>
        <div className="relative max-w-3xl">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <p className="eyebrow">LEDGER / PROJECT SPOTLIGHT</p>
            <Badge
              variant="outline"
              className="h-7 border-accent/25 bg-accent-dim px-3 text-accent"
            >
              <Layers3 className="size-3" />
              {submission.track_slug}
            </Badge>
          </div>
          <h1 className="font-display text-4xl leading-display font-medium tracking-display sm:text-5xl lg:text-6xl">
            {submission.name}
          </h1>
          {hasDistinctTagline && (
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-text-secondary">
              {submission.tagline}
            </p>
          )}
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-text-secondary">
            <span className="flex items-center gap-2">
              <UsersRound className="size-4 text-accent" />
              {submission.team_name || "Independent build"}
            </span>
            <span className="flex items-center gap-2">
              <CalendarDays className="size-4 text-accent" />
              <span className="font-mono text-xs">
                Submitted{" "}
                <ClientDate iso={submission.submitted_at} variant="short" />
              </span>
            </span>
            <Badge
              variant="outline"
              className="h-6 bg-success-dim text-success capitalize"
            >
              {submission.status}
            </Badge>
          </div>
        </div>
      </header>
      <div className="mt-10 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-12">
        <section className="rounded-2xl border border-border bg-bg-elevated p-7 sm:p-9">
          <p className="eyebrow mb-3">THE IDEA, THE BUILD, THE IMPACT</p>
          <h2 className="text-2xl font-medium tracking-tight">
            About the project
          </h2>
          <p className="mt-6 whitespace-pre-line leading-[1.85] text-text-secondary">
            {submission.description ||
              "The team hasn’t added a description yet. Explore the available project links to learn more about their build."}
          </p>
        </section>
        <aside className="space-y-6 lg:sticky lg:top-24">
          <section className="rounded-2xl border border-border bg-bg-elevated p-6">
            <h2 className="text-base font-medium">Experience the build</h2>
            {links.length ? (
              <ul className="mt-5 space-y-3">
                {links.map(({ url, title, hint, icon: Icon }) => (
                  <li key={title}>
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex items-center gap-3 rounded-xl border border-border bg-bg p-4 transition-colors hover:border-accent/40 hover:bg-accent-dim"
                    >
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-dim text-accent">
                        <Icon className="size-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium">
                          {title}
                        </span>
                        <span className="mt-1 block text-xs text-text-muted">
                          {hint}
                        </span>
                      </span>
                      <ArrowUpRight className="size-4 shrink-0 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                      <span className="sr-only"> (opens in a new tab)</span>
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-5 rounded-xl border border-dashed border-border p-5 text-sm leading-relaxed text-text-muted">
                <ExternalLink className="mb-3 size-5 text-accent" />
                No external links have been shared for this project.
              </div>
            )}
          </section>
          <section className="rounded-2xl border border-border bg-bg-elevated p-6">
            <p className="eyebrow mb-4">BUILD DETAILS</p>
            <dl className="space-y-4 text-sm">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-text-muted">Team</dt>
                <dd className="text-right">{submission.team_name || "—"}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-text-muted">Track</dt>
                <dd className="text-right">{submission.track_slug}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-text-muted">Last updated</dt>
                <dd className="text-right font-mono text-xs">
                  <ClientDate iso={submission.updated_at} variant="short" />
                </dd>
              </div>
            </dl>
          </section>
          <Link
            href="/gallery"
            className={cn(buttonVariants({ variant: "outline" }), "w-full")}
          >
            <ArrowLeft className="size-4" />
            Discover more projects
          </Link>
        </aside>
      </div>
    </article>
  );
}
