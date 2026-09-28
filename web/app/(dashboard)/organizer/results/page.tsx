import { cookies } from "next/headers";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ClientDate } from "@/components/client-date";

const RESULT_COLOR: Record<string, string> = {
  success: "text-success font-medium",
  denied: "text-destructive",
  error: "text-destructive font-semibold",
};

export default async function VotingResultsPage() {
  const cookieHeader = (await cookies()).toString();

  let votes;
  let audit;
  try {
    [votes, audit] = await Promise.all([
      api.voteResults(undefined, cookieHeader),
      api.auditLog(undefined, 100, cookieHeader),
    ]);
  } catch (err) {
    // The layout already guarantees a signed-in session — a 403 here
    // means this account just isn't an organizer, same as /organizer.
    if (err instanceof ApiError && err.status === 403) {
      return (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertTitle>Organizer role required</AlertTitle>
          <AlertDescription>
            You&apos;re signed in, but this account isn&apos;t listed as an organizer
            for this event. Ask the event owner to add you.
          </AlertDescription>
        </Alert>
      );
    }
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" />
        <AlertDescription>
          Couldn&apos;t load results or the audit log:{" "}
          {err instanceof Error ? err.message : "Unknown error."}
        </AlertDescription>
      </Alert>
    );
  }

  const topVotes = votes.results.length
    ? Math.max(...votes.results.map((r) => r.total_votes))
    : 0;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Voting results &amp; audit log</h1>
        <Link href="/organizer" className={cn(buttonVariants({ variant: "outline" }))}>
          Back to dashboard
        </Link>
      </div>

      <section>
        <h2 className="text-lg font-semibold">Results</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Mode: {votes.voting_mode} ·{" "}
          {votes.results_visible
            ? "visible (results window is open)"
            : "hidden from participants until the results window opens — you can see it as organizer"}
        </p>
        {votes.results.length === 0 ? (
          <Alert className="mt-3">
            <AlertDescription>No submitted projects yet.</AlertDescription>
          </Alert>
        ) : (
          <ol className="mt-3 flex flex-col gap-2">
            {votes.results.map((row, i) => (
              <li key={row.project_id}>
                <Card className="grid grid-cols-[2.5rem_1fr_2fr_auto] items-center gap-3 p-3">
                  <span className="font-bold text-primary">#{i + 1}</span>
                  <span className="font-medium">{row.project_name}</span>
                  <span className="block h-2 overflow-hidden rounded-full bg-muted">
                    <span
                      className="block h-full rounded-full bg-primary"
                      style={{
                        width: `${topVotes ? (row.total_votes / topVotes) * 100 : 0}%`,
                      }}
                    />
                  </span>
                  <span className="whitespace-nowrap text-right text-sm text-muted-foreground">
                    {row.total_votes} vote{row.total_votes === 1 ? "" : "s"}
                    {row.vote_count !== row.total_votes && ` (${row.vote_count} ballots)`}
                  </span>
                </Card>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold">Audit log</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Most recent 100 events, newest first.
        </p>
        {audit.entries.length === 0 ? (
          <Alert className="mt-3">
            <AlertDescription>No audit events recorded yet.</AlertDescription>
          </Alert>
        ) : (
          <Card className="mt-3">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {audit.entries.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell>
                      <ClientDate iso={entry.created_at} />
                    </TableCell>
                    <TableCell>{entry.actor_email ?? "anonymous"}</TableCell>
                    <TableCell>{entry.action}</TableCell>
                    <TableCell>
                      {entry.target_type}
                      {entry.target_id ? ` #${entry.target_id.slice(0, 8)}` : ""}
                    </TableCell>
                    <TableCell className={cn(RESULT_COLOR[entry.result])}>
                      {entry.result}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </section>
    </div>
  );
}
