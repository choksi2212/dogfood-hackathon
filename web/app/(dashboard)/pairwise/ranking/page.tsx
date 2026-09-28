import { cookies } from "next/headers";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ExportCsvButton } from "./ExportCsvButton";
import { cn } from "@/lib/utils";

export default async function PairwiseRankingPage() {
  const cookieHeader = (await cookies()).toString();

  // GET .../pairwise/ranking is IsJudge-gated same as the ballot
  // endpoint — check the role up front instead of letting a non-judge
  // hit the generic error boundary (same fix as /pairwise itself, #9).
  const user = await api.me(cookieHeader);
  const membership = user.memberships.find((m) => m.event === EVENT_SLUG);
  const canView = membership?.role === "judge" || membership?.role === "admin";

  if (!canView) {
    return (
      <Alert>
        <AlertCircle className="size-4" />
        <AlertTitle>Judges only</AlertTitle>
        <AlertDescription>
          Only judges can view the pairwise ranking. Switch accounts to participate.
        </AlertDescription>
      </Alert>
    );
  }

  const [data, gallery] = await Promise.all([
    api.pairwiseRanking(undefined, cookieHeader),
    // Ranking only has project_id (the fit doesn't carry names) — join
    // against the public gallery to show real project names instead of
    // raw UUIDs, same fix as the judge console and organizer dashboard.
    api.gallery(),
  ]);

  const namesById = new Map(gallery.items.map((p) => [p.id, p.name]));
  const rows = data.ranking.map((entry) => ({
    ...entry,
    project_name: namesById.get(entry.project_id) ?? `Project ${entry.project_id.slice(0, 8)}`,
  }));

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Pairwise ranking</h1>
          <p className="mt-1 text-muted-foreground">
            {data.n_ballots} ballots · {data.iterations} iterations ·{" "}
            {data.converged ? "converged" : "not yet converged"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {rows.length > 0 && <ExportCsvButton rows={rows} eventSlug={EVENT_SLUG} />}
          <Link href="/pairwise" className={cn(buttonVariants({ variant: "outline" }))}>
            Back to compare
          </Link>
        </div>
      </div>
      {rows.length === 0 ? (
        <Alert className="mt-6">
          <AlertDescription>No ballots cast yet.</AlertDescription>
        </Alert>
      ) : (
        <ol className="mt-6 flex flex-col gap-2">
          {rows.map((entry) => (
            <li key={entry.project_id}>
              <Card className="grid grid-cols-[3rem_1fr_auto_auto] items-center gap-3 p-3">
                <span className="font-bold text-primary">#{entry.rank}</span>
                <span className="font-medium">{entry.project_name}</span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {entry.wins}W / {entry.losses}L / {entry.ties}T
                </span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  θ {entry.theta.toFixed(3)}
                </span>
              </Card>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
