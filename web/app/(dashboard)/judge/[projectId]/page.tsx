import { cookies } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  ClipboardCheck,
  ExternalLink,
  GitBranch,
  Play,
  ShieldCheck,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { EmptyState, LoadError } from "@/components/portal-ui";
import { ClientDate } from "@/components/client-date";
import type { SubmissionDetail } from "@/lib/api/types";
import { ScoreForm } from "./ScoreForm";

export default async function JudgeScorePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const cookieHeader = (await cookies()).toString();
  let batch;
  let rubric;
  let judgeScores;
  try {
    [batch, rubric, judgeScores] = await Promise.all([
      api.meBatch(undefined, cookieHeader),
      api.rubric(undefined, cookieHeader),
      api.judgeScores(cookieHeader),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return (
        <EmptyState
          icon={ClipboardCheck}
          title="No batch assigned"
          description="The organizer assigns projects to each judge. This account doesn’t have a judging assignment for this event."
          href="/judge"
          action="Back to your batch"
        />
      );
    }
    return (
      <LoadError
        title="We couldn’t load this review"
        description="Try again to load your project, rubric, and saved scores."
        href={`/judge/${projectId}`}
      />
    );
  }

  const project = batch.projects.find((entry) => entry.id === projectId);
  if (!project) notFound();

  let details: SubmissionDetail | null = null;
  try {
    details = await api.submission(project.id);
  } catch {
    /* Keep scoring available if public project details cannot be loaded. */
  }
  const initialValues = Object.fromEntries(
    judgeScores.scores
      .filter((score) => score.project_id === project.id)
      .map((score) => [score.criterion_id, score.value]),
  );
  const links = details
    ? [
        { title: "Source code", url: details.repo_url, icon: GitBranch },
        { title: "Live project", url: details.live_url, icon: ExternalLink },
        { title: "Demo video", url: details.demo_video_url, icon: Play },
      ].filter((link) => /^https?:\/\//i.test(link.url))
    : [];

  return (
    <div>
      <Link
        href="/judge"
        className="text-link mb-8 text-sm text-text-secondary"
      >
        <ArrowLeft className="size-4" />
        Back to your batch
      </Link>
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)] lg:gap-10">
        <aside className="space-y-6 lg:sticky lg:top-24">
          <div>
            <div className="mb-5 flex items-center gap-3">
              <p className="eyebrow">PROJECT / REVIEW</p>
              {details?.track_slug && (
                <Badge
                  variant="outline"
                  className="h-auto bg-accent-dim py-1 font-mono text-xs text-accent"
                >
                  {details.track_slug.replace(/-/g, " ")}
                </Badge>
              )}
            </div>
            <h1 className="font-display text-4xl leading-tight font-medium tracking-display sm:text-5xl">
              {project.name}
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-text-secondary">
              {project.tagline}
            </p>
          </div>
          <section className="surface p-6">
            <h2 className="mb-4 text-sm font-medium">About the project</h2>
            {details ? (
              <p className="whitespace-pre-wrap text-sm leading-7 text-text-secondary">
                {details.description ||
                  "This project has no additional description. Explore the submitted links for more context."}
              </p>
            ) : (
              <LoadError
                title="Project details are unavailable"
                description="You can still review with the rubric. Refresh to try loading the description and links again."
                href={`/judge/${projectId}`}
              />
            )}
            {details?.team_name && (
              <div className="mt-6 border-t pt-5">
                <p className="eyebrow text-xs text-text-muted">BUILT BY</p>
                <p className="mt-2 text-sm">{details.team_name}</p>
              </div>
            )}
          </section>
          {links.length > 0 && (
            <section className="surface p-6">
              <h2 className="mb-4 text-sm font-medium">Explore the work</h2>
              <div className="space-y-3">
                {links.map(({ title, url, icon: Icon }) => (
                  <a
                    key={title}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex min-h-12 items-center gap-3 rounded-xl border bg-bg p-3 text-sm transition-colors hover:border-accent/50 hover:bg-accent-dim"
                  >
                    <Icon className="size-4 text-accent" />
                    <span className="flex-1">{title}</span>
                    <ArrowUpRight className="size-4 text-text-muted" />
                    <span className="sr-only"> opens in a new tab</span>
                  </a>
                ))}
              </div>
            </section>
          )}
          <div className="flex items-start gap-3 rounded-xl border border-dashed p-5 text-xs leading-relaxed text-text-secondary">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" />
            <p>
              Your scores are private to the judging process. Evaluate each
              criterion independently and include feedback that helps the team.
            </p>
          </div>
          {details?.submitted_at && (
            <p className="text-xs text-text-muted">
              Project submitted{" "}
              <ClientDate iso={details.submitted_at} className="font-mono" />
            </p>
          )}
        </aside>
        <ScoreForm
          projectId={project.id}
          criteria={rubric.criteria}
          initialValues={initialValues}
          initialSubmittedAt={project.submitted_at}
        />
      </div>
    </div>
  );
}
