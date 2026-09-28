import { cookies } from "next/headers";
import Link from "next/link";
import {
  ArrowRight,
  CalendarClock,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { PageHeading, EmptyState, LoadError } from "@/components/portal-ui";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { ClientDate } from "@/components/client-date";
import { cn } from "@/lib/cn";
import { OrganizerActions } from "./actions";
import { MembershipTable } from "./MembershipTable";
import { StatCard } from "./StatCard";

export default async function OrganizerPage() {
  const cookieHeader = (await cookies()).toString();
  let event;
  let memberships;
  let submissions;
  try {
    [event, memberships, submissions] = await Promise.all([
      api.eventDetail(undefined, cookieHeader),
      api.memberships(undefined, cookieHeader),
      api
        .allGallery()
        .then((projects) => projects.length)
        .catch(() => null),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      return (
        <EmptyState
          icon={ShieldCheck}
          title="Organizer access required"
          description="Your account needs an organizer role for this event. Ask the event owner to add you, or switch to your organizer account."
          href="/login"
          action="Switch accounts"
        />
      );
    }
    return (
      <LoadError
        title="We couldn’t load your event"
        description="Event data is temporarily unavailable. Refresh to try again."
        href="/organizer"
      />
    );
  }
  const counts = memberships.reduce<Record<string, number>>(
    (result, member) => {
      result[member.role] = (result[member.role] ?? 0) + 1;
      return result;
    },
    {},
  );

  return (
    <div className="space-y-10">
      <PageHeading
        eyebrow="EVENT CONTROL / ORGANIZER"
        title={event.name}
        description={
          event.description ||
          "Everything you need to run a fair, thoughtful judging cycle."
        }
        action={
          <Link
            href="/organizer/results"
            className={cn(buttonVariants({ variant: "outline" }), "shrink-0")}
          >
            Results &amp; audit
            <ArrowRight className="size-4" />
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Judges"
          value={counts.judge ?? 0}
          detail="Reviewers on your event"
          index={0}
        />
        <StatCard
          label="Organizers"
          value={counts.organizer ?? 0}
          detail="Keeping everything on track"
          index={1}
        />
        <StatCard
          label="Participants"
          value={counts.participant ?? 0}
          detail="Builders with event access"
          index={2}
        />
        <StatCard
          label="Submissions"
          value={submissions}
          detail={
            submissions === null
              ? "Gallery count temporarily unavailable"
              : "Published in the gallery"
          }
          index={3}
        />
      </div>

      <section
        aria-label="Event schedule"
        className="surface grid gap-6 rounded-2xl p-6 sm:grid-cols-2 xl:grid-cols-4"
      >
        <div>
          <p className="mb-3 flex items-center gap-2 text-xs text-text-muted">
            <CalendarClock className="size-4" />
            Event status
          </p>
          <Badge
            className="rounded-full border-accent/25 bg-accent-dim px-3 py-1 text-accent capitalize"
            variant="outline"
          >
            {event.state.replaceAll("_", " ")}
          </Badge>
        </div>
        <div>
          <p className="mb-3 text-xs text-text-muted">Submissions close</p>
          <p className="font-mono text-xs leading-6">
            <ClientDate iso={event.submissions_close_at} />
          </p>
        </div>
        <div>
          <p className="mb-3 text-xs text-text-muted">Judging window</p>
          <div className="font-mono text-xs leading-6">
            <ClientDate iso={event.judging_open_at} />
            <span className="mx-1 text-text-muted">→</span>
            <ClientDate iso={event.judging_close_at} />
          </div>
        </div>
        <div>
          <p className="mb-3 flex items-center gap-2 text-xs text-text-muted">
            <SlidersHorizontal className="size-4" />
            Voting mode
          </p>
          <p className="text-sm capitalize">{event.voting_mode}</p>
          <p className="mt-1 text-xs text-text-muted">
            {event.tracks.length} tracks · {event.rubric?.criteria.length ?? 0}{" "}
            scoring criteria
          </p>
        </div>
      </section>

      <MembershipTable memberships={memberships} />

      <section aria-labelledby="operations-title">
        <div className="mb-5">
          <p className="eyebrow mb-2">MAKE IT HAPPEN</p>
          <h2
            id="operations-title"
            className="text-2xl font-medium tracking-tight"
          >
            Event operations
          </h2>
          <p className="mt-2 text-sm text-text-secondary">
            Invite your panel, distribute projects, and prepare scores for
            review.
          </p>
        </div>
        <OrganizerActions />
      </section>
    </div>
  );
}
