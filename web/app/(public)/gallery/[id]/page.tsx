import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ClientDate } from "@/components/client-date";

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
    // 404 → render the framework not-found so the navbar/back button
    // still works. Anything else → render an error card with the actual
    // message so the user knows what broke (e.g. backend down).
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {err instanceof Error ? err.message : "Couldn't load this submission."}
        </AlertDescription>
      </Alert>
    );
  }

  const hasDistinctTagline = submission.tagline && submission.tagline !== submission.name;
  const hasLinks = submission.repo_url || submission.live_url || submission.demo_video_url;

  return (
    <article className="mx-auto max-w-2xl">
      <Link
        href="/gallery"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Back to gallery
      </Link>

      <header className="mt-6 mb-6">
        <Badge variant="secondary" className="mb-2">
          {submission.track_slug}
        </Badge>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{submission.name}</h1>
        {hasDistinctTagline && (
          <p className="mt-2 text-lg text-muted-foreground">{submission.tagline}</p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>{submission.team_name}</span>
          <span aria-hidden="true">·</span>
          <span>
            Submitted <ClientDate iso={submission.submitted_at} variant="short" />
          </span>
          <span aria-hidden="true">·</span>
          <Badge className="capitalize">{submission.status}</Badge>
        </div>
      </header>

      {submission.description && (
        <section className="mb-6 border-t pt-4">
          <h2 className="mb-3 text-lg font-semibold">About the project</h2>
          <p className="whitespace-pre-line leading-relaxed">{submission.description}</p>
        </section>
      )}

      {hasLinks && (
        <section className="mb-6 border-t pt-4">
          <h2 className="mb-3 text-lg font-semibold">Links</h2>
          <ul className="flex flex-col gap-2">
            {submission.demo_video_url && (
              <li>
                <a
                  href={submission.demo_video_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                >
                  Demo video <ExternalLink className="size-3.5" />
                </a>
              </li>
            )}
            {submission.repo_url && (
              <li>
                <a
                  href={submission.repo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                >
                  Source <ExternalLink className="size-3.5" />
                </a>
              </li>
            )}
            {submission.live_url && (
              <li>
                <a
                  href={submission.live_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                >
                  Live site <ExternalLink className="size-3.5" />
                </a>
              </li>
            )}
          </ul>
        </section>
      )}

      <footer className="border-t pt-4">
        <Link
          href="/gallery"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> Back to gallery
        </Link>
      </footer>
    </article>
  );
}
