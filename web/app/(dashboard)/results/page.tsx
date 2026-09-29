import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CheckCircle2, ClipboardList, Timer, Trophy } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
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
import { EmptyState, LoadError, PageHeading } from "@/components/portal-ui";
import { cn } from "@/lib/cn";

// /results is the documented results route (PRD §3.3 FR-230/FR-231 and
// the "Visitors see results at /{event_slug}/results" story): it is a
// session-gated view over /api/events/<slug>/votes/results. The
// (dashboard) layout 307s unauthenticated visitors to /login; signed-in
// non-organizers see a friendly seal until `results_at` passes, then
// the live tally — organizers see it immediately with its live/published
// state.

export default async function ResultsPage() {
  const cookieHeader = (await cookies()).toString();

  let data;
  try {
    data = await api.voteResults(undefined, cookieHeader);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    if (err instanceof ApiError && err.status === 403) {
      return (
        <>
          <PageHeading
            eyebrow="EVENT / RESULTS"
            title="Results"
            description="Community tallies publish the moment the event closes."
          />
          <EmptyState
            icon={ClipboardList}
            title="Results are still sealed"
            description="Tallies go live for everyone as soon as results are published. Browse the gallery while you wait."
            href="/gallery"
            action="Browse projects"
          />
        </>
      );
    }
    return (
      <LoadError
        title="We couldn’t load the results"
        description="Please try again — your votes are safe."
        href="/results"
      />
    );
  }

  const topVotes = Math.max(0, ...data.results.map((row) => row.total_votes));

  return (
    <div>
      <PageHeading
        eyebrow="EVENT / RESULTS"
        title="Results"
        description="Live community tallies across every submitted project."
        action={
          <Badge
            variant="outline"
            className={cn(
              "h-auto gap-1.5 border-transparent py-1.5",
              data.results_visible
                ? "bg-success-dim text-success"
                : "bg-accent-dim text-accent",
            )}
          >
            {data.results_visible ? (
              <CheckCircle2 />
            ) : (
              <Timer className="size-3.5" />
            )}
            {data.results_visible ? "Published" : "Live for organizers"}
          </Badge>
        }
      />
      {data.results.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="The results will land here"
          description="Tallies appear once projects are submitted and voting opens. Check back when the event is underway."
          href="/gallery"
          action="Open the gallery"
        />
      ) : (
        <div className="surface overflow-hidden [&_[data-slot=table-container]]:max-h-[65vh] [&_[data-slot=table-container]]:overflow-auto">
          <Table>
            <TableCaption className="sr-only">
              Community voting results, vote totals, and ballots per project
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6" scope="col">
                  Rank
                </TableHead>
                <TableHead scope="col">Project</TableHead>
                <TableHead scope="col">Relative votes</TableHead>
                <TableHead className="text-right" scope="col">
                  Votes
                </TableHead>
                <TableHead className="pr-6 text-right" scope="col">
                  Total votes
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.results.map((row, index) => (
                <TableRow key={row.project_id}>
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
                      className="text-link font-medium"
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
                  <TableCell className="text-right font-mono tabular-nums text-success">
                    {row.vote_count}
                  </TableCell>
                  <TableCell className="pr-6 text-right font-mono tabular-nums">
                    {row.total_votes}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <p className="mt-4 text-xs leading-relaxed text-text-muted">
        Tallies update live. Retracted ballots don’t count; organizers can
        always see the standings, everyone else sees them once results are
        published.
      </p>
      <p className="mt-6">
        <Link
          href="/dashboard"
          className={buttonVariants({ variant: "outline" })}
        >
          Back to dashboard
        </Link>
      </p>
    </div>
  );
}
