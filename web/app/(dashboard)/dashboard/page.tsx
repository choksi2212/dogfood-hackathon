import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  ClipboardList,
  LayoutDashboard,
  LayoutGrid,
  ListChecks,
  Rocket,
  Scale,
  ThumbsUp,
  Trophy,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { PageHeading } from "@/components/portal-ui";

// PRD S-010 (docs/PRD.md §9.2): /dashboard is the role-aware landing —
// one tile per surface the signed-in account can actually use. The role
// resolution mirrors the (dashboard) layout's nav logic exactly, so the
// tiles can never advertise a route the sidebar doesn't.

type Tile = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

const EXPLORE_TILES: Tile[] = [
  {
    href: "/gallery",
    label: "Project gallery",
    description: "Browse every submitted project.",
    icon: LayoutGrid,
  },
  {
    href: "/vote",
    label: "Community voting",
    description: "Back the projects you believe in.",
    icon: ThumbsUp,
  },
  {
    href: "/results",
    label: "Results",
    description: "Live tallies once the event publishes.",
    icon: Trophy,
  },
];

const PARTICIPANT_TILES: Tile[] = [
  {
    href: "/submit",
    label: "Submit",
    description: "Ship your project before the deadline.",
    icon: Rocket,
  },
];

const JUDGE_TILES: Tile[] = [
  {
    href: "/judge",
    label: "My batch",
    description: "Review the projects assigned to you.",
    icon: ListChecks,
  },
  {
    href: "/pairwise",
    label: "Pairwise compare",
    description: "Head-to-head calls between projects.",
    icon: Scale,
  },
  {
    href: "/pairwise/ranking",
    label: "Pairwise ranking",
    description: "How every comparison adds up.",
    icon: BarChart3,
  },
];

const ORGANIZER_TILES: Tile[] = [
  {
    href: "/organizer",
    label: "Event overview",
    description: "Members, schedule, and operations.",
    icon: LayoutDashboard,
  },
  {
    href: "/organizer/results",
    label: "Results & audit",
    description: "Vote tallies and the audit trail.",
    icon: ClipboardList,
  },
];

function TileSection({
  id,
  title,
  tiles,
}: {
  id: string;
  title: string;
  tiles: Tile[];
}) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-4 text-xl font-medium tracking-tight">
        {title}
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map((tile) => (
          <Link
            key={tile.href}
            href={tile.href}
            className="surface group flex items-start gap-4 rounded-2xl p-6 transition-colors hover:border-accent/40 focus-visible:rounded-xl focus-visible:outline-2 focus-visible:outline-accent"
          >
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent-dim text-accent">
              <tile.icon className="size-5" />
            </span>
            <span className="flex-1">
              <span className="flex items-center gap-2 font-medium">
                {tile.label}
                <ArrowRight className="size-4 text-text-muted transition-transform group-hover:translate-x-0.5" />
              </span>
              <span className="mt-1 block text-sm leading-relaxed text-text-secondary">
                {tile.description}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default async function DashboardPage() {
  const cookieHeader = (await cookies()).toString();

  let user;
  try {
    user = await api.me(cookieHeader);
  } catch (err) {
    // The (dashboard) layout already redirects unauthenticated
    // sessions to /login; this guard covers anything it didn't catch.
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  const membership = user.memberships.find((m) => m.event === EVENT_SLUG);
  const role = membership?.role ?? "participant";
  const isParticipant = role === "participant" || role === "admin";
  const isJudge = role === "judge";
  const isOrganizer = role === "organizer" || role === "admin";

  return (
    <div className="space-y-10">
      <PageHeading
        eyebrow="HACK HAMSTER / DASHBOARD"
        title={`Welcome back, ${user.name.split(" ")[0]}`}
        description="Every surface your account can reach on this event, one click away."
      />
      <TileSection id="explore-title" title="Explore" tiles={EXPLORE_TILES} />
      {isParticipant && (
        <TileSection
          id="participant-title"
          title="Participant"
          tiles={PARTICIPANT_TILES}
        />
      )}
      {isJudge && (
        <TileSection id="judge-title" title="Judge" tiles={JUDGE_TILES} />
      )}
      {isOrganizer && (
        <TileSection
          id="organizer-title"
          title="Organizer"
          tiles={ORGANIZER_TILES}
        />
      )}
    </div>
  );
}
