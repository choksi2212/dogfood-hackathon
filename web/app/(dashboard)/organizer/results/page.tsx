import { cookies } from "next/headers";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Eye,
  EyeOff,
  ShieldCheck,
  ShieldX,
  Trophy,
  Users,
  Vote,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { PageHeading, EmptyState, LoadError } from "@/components/portal-ui";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/cn";
import { ClientDate } from "@/components/client-date";

const resultStyles = {
  success: "border-success/25 bg-success-dim text-success",
  denied: "border-error/25 bg-error-dim text-error",
  error: "border-error/25 bg-error-dim font-semibold text-error",
};
const resultIcons = {
  success: CheckCircle2,
  denied: ShieldX,
  error: CircleAlert,
};

export default async function VotingResultsPage() {
  const cookieHeader = (await cookies()).toString();
  const loaded = await Promise.allSettled([
    api.voteResults(undefined, cookieHeader),
    api.auditLog(undefined, 100, cookieHeader),
  ]);
  if (
    loaded.some(
      (item) =>
        item.status === "rejected" &&
        item.reason instanceof ApiError &&
        item.reason.status === 403,
    )
  ) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Organizer access required"
        description="Results and audit records are available to event organizers. Ask the event owner to add you, or switch to your organizer account."
        href="/login"
        action="Switch accounts"
      />
    );
  }
  const votes = loaded[0].status === "fulfilled" ? loaded[0].value : null;
  const audit = loaded[1].status === "fulfilled" ? loaded[1].value : null;
  const topVotes = votes?.results.length
    ? Math.max(...votes.results.map((row) => row.total_votes))
    : 0;
  const totalVotes =
    votes?.results.reduce((total, row) => total + row.total_votes, 0) ?? 0;
  const totalBallots =
    votes?.results.reduce((total, row) => total + row.vote_count, 0) ?? 0;

  return (
    <div className="space-y-10">
      <PageHeading
        eyebrow="EVENT CONTROL / RESULTS"
        title="Results & audit"
        description="See the community’s picks and the record behind every event decision."
        action={
          <Link
            href="/organizer"
            className={buttonVariants({ variant: "outline" })}
          >
            <ArrowLeft className="size-4" />
            Event dashboard
          </Link>
        }
      />

      {votes && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { title: "Total votes", value: totalVotes, icon: Vote },
            { title: "Recorded ballots", value: totalBallots, icon: Users },
            {
              title: "Projects in results",
              value: votes.results.length,
              icon: Trophy,
            },
          ].map(({ title, value, icon: Icon }) => (
            <div key={title} className="surface rounded-xl p-5">
              <div className="flex items-center justify-between text-sm text-text-secondary">
                <span>{title}</span>
                <Icon className="size-4 text-accent" />
              </div>
              <p className="mt-4 font-mono text-3xl tabular-nums">
                {value.toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}

      <section aria-labelledby="voting-title">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="eyebrow mb-2">COMMUNITY SIGNAL</p>
            <h2
              id="voting-title"
              className="text-2xl font-medium tracking-tight"
            >
              Voting results
            </h2>
            <p className="mt-2 text-sm text-text-secondary">
              {votes
                ? votes.voting_mode === "quadratic"
                  ? "Quadratic voting · votes reflect community credit allocation."
                  : "Simple voting · every ballot contributes one vote."
                : "Project rankings and community vote totals."}
            </p>
          </div>
          {votes && (
            <Badge
              variant="outline"
              className={cn(
                "gap-1.5 rounded-full px-3 py-1.5",
                votes.results_visible
                  ? "border-success/25 bg-success-dim text-success"
                  : "border-accent/25 bg-accent-dim text-accent",
              )}
            >
              {votes.results_visible ? (
                <Eye className="size-3" />
              ) : (
                <EyeOff className="size-3" />
              )}
              {votes.results_visible ? "Results public" : "Organizer preview"}
            </Badge>
          )}
        </div>
        {!votes ? (
          <LoadError
            title="Voting results are unavailable"
            description="Please try again to load the latest community totals."
            href="/organizer/results"
          />
        ) : votes.results.length === 0 ? (
          <EmptyState
            icon={Vote}
            title="The votes will land here"
            description="Voting results appear when projects are submitted. Keep this view handy during the voting window."
            href="/gallery"
            action="Open the gallery"
          />
        ) : (
          <div className="surface overflow-hidden rounded-2xl [&_[data-slot=table-container]]:max-h-[520px] [&_[data-slot=table-container]]:overflow-auto">
            <Table className="min-w-[680px]">
              <TableCaption className="sr-only">
                Community voting rankings, vote totals, and ballot counts
              </TableCaption>
              <TableHeader className="sticky top-0 z-10 bg-bg-elevated">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-12 pl-6 text-xs text-text-muted">
                    Rank
                  </TableHead>
                  <TableHead className="text-xs text-text-muted">
                    Project
                  </TableHead>
                  <TableHead className="text-xs text-text-muted">
                    Relative votes
                  </TableHead>
                  <TableHead className="text-right text-xs text-text-muted">
                    Ballots
                  </TableHead>
                  <TableHead className="pr-6 text-right text-xs text-text-muted">
                    Total votes
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {votes.results.map((row, index) => (
                  <TableRow
                    key={row.project_id}
                    className={cn(
                      "hover:bg-bg-overlay",
                      index % 2 ? "bg-bg-elevated" : "bg-bg",
                    )}
                  >
                    <TableCell className="py-5 pl-6">
                      <span
                        className={cn(
                          "flex items-center gap-2 font-mono text-sm tabular-nums",
                          index < 3 ? "text-accent-2" : "text-text-muted",
                        )}
                      >
                        {index < 3 && <Trophy className="size-3.5" />}
                        <span className="sr-only">Rank </span>
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/gallery/${row.project_id}`}
                        className="font-medium transition-colors hover:text-accent focus-visible:rounded focus-visible:outline-2 focus-visible:outline-accent"
                      >
                        {row.project_name}
                      </Link>
                      <p
                        className="mt-1 font-mono text-xs text-text-muted"
                        title={row.project_id}
                      >
                        {row.project_id.slice(0, 8)}
                      </p>
                    </TableCell>
                    <TableCell>
                      <div
                        className="h-1.5 w-28 overflow-hidden rounded-full bg-bg-overlay"
                        aria-label={`${topVotes ? Math.round((row.total_votes / topVotes) * 100) : 0}% of the top project's votes`}
                      >
                        <div
                          className="h-full origin-left rounded-full bg-accent"
                          style={{
                            transform: `scaleX(${topVotes ? row.total_votes / topVotes : 0})`,
                          }}
                        />
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm text-text-secondary tabular-nums">
                      {row.vote_count.toLocaleString()}
                    </TableCell>
                    <TableCell className="pr-6 text-right font-mono text-lg tabular-nums">
                      {row.total_votes.toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="border-t px-6 py-3 text-xs text-text-muted">
              {votes.results_visible
                ? "The results window is open. Participants can see these totals."
                : "These totals are private to organizers until the results window opens."}
            </div>
          </div>
        )}
      </section>

      <section aria-labelledby="audit-title">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow mb-2">EVERY ACTION, ACCOUNTED FOR</p>
            <h2
              id="audit-title"
              className="text-2xl font-medium tracking-tight"
            >
              Audit log
            </h2>
            <p className="mt-2 text-sm text-text-secondary">
              Most recent 100 event records, newest first.
            </p>
          </div>
          <Badge
            variant="outline"
            className="gap-1.5 rounded-full px-3 py-1.5 text-text-secondary"
          >
            <ShieldCheck className="size-3.5" />
            Recorded by the platform
          </Badge>
        </div>
        {!audit ? (
          <LoadError
            title="The audit log is unavailable"
            description="Please try again to load the latest event records."
            href="/organizer/results"
          />
        ) : audit.entries.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="A clean slate"
            description="The audit log records votes, reviews, and organizer actions as they happen."
          />
        ) : (
          <div className="surface overflow-hidden rounded-2xl [&_[data-slot=table-container]]:max-h-[520px] [&_[data-slot=table-container]]:overflow-auto">
            <Table className="min-w-[830px]">
              <TableCaption className="sr-only">
                Event audit log: timestamp, actor, action, target, and result
              </TableCaption>
              <TableHeader className="sticky top-0 z-10 bg-bg-elevated">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-12 pl-6 text-xs text-text-muted">
                    Timestamp
                  </TableHead>
                  <TableHead className="text-xs text-text-muted">
                    Actor
                  </TableHead>
                  <TableHead className="text-xs text-text-muted">
                    Action
                  </TableHead>
                  <TableHead className="text-xs text-text-muted">
                    Target
                  </TableHead>
                  <TableHead className="pr-6 text-right text-xs text-text-muted">
                    Result
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {audit.entries.map((entry, index) => {
                  const ResultIcon = resultIcons[entry.result];
                  return (
                    <TableRow
                      key={entry.id}
                      className={cn(
                        "hover:bg-bg-overlay",
                        index % 2 ? "bg-bg-elevated" : "bg-bg",
                      )}
                    >
                      <TableCell className="py-4 pl-6 font-mono text-xs text-text-secondary tabular-nums">
                        <ClientDate iso={entry.created_at} />
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.actor_email ?? (
                          <span className="text-text-muted">
                            Anonymous visitor
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-text-secondary">
                        {entry.action}
                      </TableCell>
                      <TableCell>
                        <p className="text-xs text-text-secondary">
                          {entry.target_type || "—"}
                        </p>
                        {entry.target_id && (
                          <p
                            className="mt-1 font-mono text-xs text-text-muted"
                            title={entry.target_id}
                          >
                            {entry.target_id.slice(0, 8)}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="pr-6 text-right">
                        <Badge
                          variant="outline"
                          className={cn(
                            "gap-1.5 rounded-full px-2.5 py-1 text-xs capitalize",
                            resultStyles[entry.result],
                          )}
                        >
                          <ResultIcon className="size-3" />
                          {entry.result}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            <div className="border-t px-6 py-3 font-mono text-xs text-text-muted">
              {audit.entries.length} recorded event
              {audit.entries.length === 1 ? "" : "s"}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
