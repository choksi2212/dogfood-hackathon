import { cookies } from "next/headers";
import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Scale,
  Trophy,
} from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
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
import { ExportCsvButton } from "./ExportCsvButton";
import { cn } from "@/lib/cn";

export default async function PairwiseRankingPage() {
  const cookieHeader = (await cookies()).toString();
  const user = await api.me(cookieHeader);
  const membership = user.memberships.find(
    (entry) => entry.event === EVENT_SLUG,
  );
  const canView = membership?.role === "judge" || membership?.role === "admin";

  if (!canView)
    return (
      <>
        <PageHeading
          eyebrow="JUDGING / THE BIG PICTURE"
          title="Pairwise ranking"
          description="See how every comparison adds up."
        />
        <EmptyState
          icon={Scale}
          title="A space for judges"
          description="Only judges can view the pairwise ranking. Sign in with your judge account to participate."
          href="/login"
          action="Switch accounts"
        />
      </>
    );

  let data;
  let gallery;
  try {
    [data, gallery] = await Promise.all([
      api.pairwiseRanking(undefined, cookieHeader),
      api.allGallery(),
    ]);
  } catch {
    return (
      <LoadError
        title="We couldn’t load the ranking"
        description="Try again to see the latest pairwise results."
        href="/pairwise/ranking"
      />
    );
  }

  const namesById = new Map(
    gallery.map((project) => [project.id, project.name]),
  );
  const rows = data.ranking.map((entry) => ({
    ...entry,
    project_name:
      namesById.get(entry.project_id) ??
      `Project ${entry.project_id.slice(0, 8)}`,
  }));
  const maxTheta = Math.max(0.0001, ...rows.map((entry) => entry.theta));

  return (
    <div>
      <PageHeading
        eyebrow="JUDGING / THE BIG PICTURE"
        title="Pairwise ranking"
        description="A collective perspective, built one comparison at a time. Relative strength is fitted with the Bradley–Terry model."
        action={
          <div className="flex flex-wrap items-center gap-3">
            {rows.length > 0 && (
              <ExportCsvButton rows={rows} eventSlug={EVENT_SLUG} />
            )}
            <Link
              href="/pairwise"
              className={buttonVariants({ variant: "outline" })}
            >
              <ArrowLeft className="size-4" />
              Back to compare
            </Link>
          </div>
        }
      />
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <div className="surface p-5">
          <p className="eyebrow text-xs text-text-muted">
            COMPARISONS RECORDED
          </p>
          <p className="mt-3 font-mono text-3xl tabular-nums">
            {data.n_ballots.toLocaleString("en-US")}
          </p>
          <p className="mt-2 text-xs text-text-secondary">
            Each ballot contributes to the fit.
          </p>
        </div>
        <div className="surface p-5">
          <p className="eyebrow text-xs text-text-muted">PROJECTS RANKED</p>
          <p className="mt-3 font-mono text-3xl tabular-nums">{rows.length}</p>
          <p className="mt-2 text-xs text-text-secondary">
            Projects represented in this ranking.
          </p>
        </div>
        <div className="surface p-5">
          <p className="eyebrow text-xs text-text-muted">MODEL STATUS</p>
          <div className="mt-4">
            <Badge
              variant="outline"
              className={cn(
                "h-auto gap-1.5 border-transparent py-1.5",
                data.converged
                  ? "bg-success-dim text-success"
                  : "bg-accent-dim text-accent",
              )}
            >
              {data.converged && <CheckCircle2 />}
              {data.converged ? "Fit converged" : "Fit in progress"}
            </Badge>
          </div>
          <p className="mt-3 font-mono text-xs text-text-secondary">
            {data.iterations} iterations
          </p>
        </div>
      </div>
      {rows.length === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="The ranking starts with a choice"
          description="No projects are ranked yet. Compare the first pair to help build the collective picture."
          href="/pairwise"
          action="Start comparing"
        />
      ) : (
        <>
          <div className="surface overflow-hidden [&_[data-slot=table-container]]:max-h-[65vh] [&_[data-slot=table-container]]:overflow-auto">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-5 sm:px-6">
              <h2 className="font-medium">The leaderboard</h2>
              <span className="font-mono text-xs uppercase tracking-caps text-text-muted">
                RELATIVE STRENGTH · θ
              </span>
            </div>
            <Table>
              <TableCaption className="sr-only">
                Pairwise project ranking, wins, losses, ties, and Bradley–Terry
                relative strength.
              </TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6" scope="col">
                    Rank
                  </TableHead>
                  <TableHead scope="col">Project</TableHead>
                  <TableHead className="text-right" scope="col">
                    Wins
                  </TableHead>
                  <TableHead className="text-right" scope="col">
                    Losses
                  </TableHead>
                  <TableHead className="text-right" scope="col">
                    Ties
                  </TableHead>
                  <TableHead className="min-w-48 pr-6" scope="col">
                    Strength · θ
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((entry) => (
                  <TableRow key={entry.project_id}>
                    <TableCell className="pl-6">
                      <span
                        className={cn(
                          "flex items-center gap-2 font-mono tabular-nums",
                          entry.rank <= 3
                            ? "text-accent-2"
                            : "text-text-secondary",
                        )}
                      >
                        {entry.rank <= 3 ? (
                          <Trophy
                            className="size-4"
                            aria-label="Top three project"
                          />
                        ) : (
                          <span className="size-4" aria-hidden="true" />
                        )}
                        <span>{String(entry.rank).padStart(2, "0")}</span>
                      </span>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/gallery/${entry.project_id}`}
                        className="text-link font-medium"
                      >
                        {entry.project_name}
                      </Link>
                      <p className="mt-1 font-mono text-xs text-text-muted">
                        {entry.project_id.slice(0, 8)}
                      </p>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-success">
                      {entry.wins}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-text-secondary">
                      {entry.losses}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-text-secondary">
                      {entry.ties}
                    </TableCell>
                    <TableCell className="pr-6">
                      <div className="flex items-center gap-4">
                        <span className="w-14 shrink-0 font-mono text-sm tabular-nums">
                          {entry.theta.toFixed(3)}
                        </span>
                        <span
                          className="relative h-1.5 w-24 overflow-hidden rounded-full bg-bg-overlay"
                          aria-hidden="true"
                        >
                          <span
                            className="absolute inset-0 origin-left rounded-full bg-accent"
                            style={{
                              transform: `scaleX(${Math.max(0, entry.theta) / maxTheta})`,
                            }}
                          />
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <p className="mt-4 flex items-start gap-2 text-xs leading-relaxed text-text-muted">
            <Scale className="mt-0.5 size-3.5 shrink-0" />θ describes relative
            strength in this model. Pairwise comparisons complement the rubric;
            they don’t replace a project’s criterion scores.
          </p>
        </>
      )}
    </div>
  );
}
