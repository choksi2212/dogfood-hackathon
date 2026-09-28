import { cookies } from "next/headers";
import Link from "next/link";
import { AlertCircle, ArrowRight, Download } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { AssignmentPanel, BulkInvitePanel, NormalizationPanel } from "./actions";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ClientDate } from "@/components/client-date";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default async function OrganizerPage() {
  const cookieHeader = (await cookies()).toString();

  let event;
  let memberships;
  try {
    [event, memberships] = await Promise.all([
      api.eventDetail(undefined, cookieHeader),
      api.memberships(undefined, cookieHeader),
    ]);
  } catch (err) {
    // The layout already guarantees a signed-in session — a 403 here
    // means this account just isn't an organizer for this event.
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
          Couldn&apos;t load the dashboard:{" "}
          {err instanceof Error ? err.message : "Unknown error."}
        </AlertDescription>
      </Alert>
    );
  }

  const roleCounts = memberships.reduce<Record<string, number>>((acc, m) => {
    acc[m.role] = (acc[m.role] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{event.name}</h1>
          <p className="mt-1 max-w-xl text-muted-foreground">{event.description}</p>
        </div>
        <Link
          href="/organizer/results"
          className={cn(buttonVariants({ variant: "outline" }))}
        >
          Voting results &amp; audit log <ArrowRight className="size-4" />
        </Link>
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">State</span>
            <span>{event.state}</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Submissions close
            </span>
            <span>
              <ClientDate iso={event.submissions_close_at} />
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Judging window
            </span>
            <span>
              <ClientDate iso={event.judging_open_at} /> –{" "}
              <ClientDate iso={event.judging_close_at} />
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Voting mode
            </span>
            <span>{event.voting_mode}</span>
          </div>
        </CardContent>
      </Card>

      <section>
        <h2 className="text-lg font-semibold">Membership</h2>
        <div className="mt-3 flex gap-2">
          {Object.entries(roleCounts).map(([role, count]) => (
            <Badge key={role} variant="secondary">
              {count} {role}
              {count === 1 ? "" : "s"}
            </Badge>
          ))}
        </div>
        <Card className="mt-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {memberships.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{m.user_name}</TableCell>
                  <TableCell>{m.user_email}</TableCell>
                  <TableCell className="capitalize">{m.role}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </section>

      <section>
        <h2 className="text-lg font-semibold">Actions</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <BulkInvitePanel />
          <AssignmentPanel />
          <NormalizationPanel />
          <Card>
            <CardHeader>
              <CardTitle>Export</CardTitle>
              <CardDescription>
                Download the current scores as CSV for offline review.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <a
                href={api.csvExportUrl()}
                download
                className={cn(buttonVariants())}
              >
                <Download className="size-4" />
                Export scores (CSV)
              </a>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
