import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import {
  SidebarProvider,
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarInset,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { DashboardNav, type NavGroup } from "@/components/dashboard-nav";
import { SidebarUser } from "@/components/sidebar-user";
import { ThemeToggle } from "@/components/theme-toggle";
import { Brand } from "@/components/brand";
import { DashboardTitle } from "@/components/dashboard-title";
import { PageTransition } from "@/components/page-transition";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieHeader = (await cookies()).toString();

  let user;
  try {
    user = await api.me(cookieHeader);
  } catch (err) {
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

  // Vote is deliberately public to any signed-in account (the API is
  // AllowAny) — an audience vote alongside judged scoring is by design,
  // so judges and organizers keep it. Submit is not: POST .../submit
  // requires IsParticipant, so showing it to a judge/organizer would
  // dangle a control that just 403s — same mistake #9 fixed for
  // /pairwise, applied here too.
  const groups: NavGroup[] = [
    {
      label: "Home",
      items: [
        {
          href: "/dashboard",
          label: "My dashboard",
          icon: "layoutDashboard",
        },
      ],
    },
    {
      label: "Explore",
      items: [{ href: "/gallery", label: "Project gallery", icon: "gallery" }],
    },
  ];
  if (isParticipant) {
    groups.push({
      label: "Participant",
      items: [{ href: "/submit", label: "Submit", icon: "rocket" }],
    });
  }
  groups.push({
    label: "Vote",
    items: [{ href: "/vote", label: "Vote", icon: "thumbsUp" }],
  });
  if (isJudge) {
    groups.push({
      label: "Judge",
      items: [
        { href: "/judge", label: "My batch", icon: "listChecks" },
        { href: "/pairwise", label: "Pairwise compare", icon: "scale" },
        {
          href: "/pairwise/ranking",
          label: "Pairwise ranking",
          icon: "barChart",
        },
      ],
    });
  }
  if (isOrganizer) {
    groups.push({
      label: "Organizer",
      items: [
        { href: "/organizer", label: "Event overview", icon: "layoutDashboard" },
        {
          href: "/organizer/results",
          label: "Results & audit",
          icon: "clipboardList",
        },
      ],
    });
  }

  return (
    <SidebarProvider>
      <Sidebar
        collapsible="icon"
        className="border-r border-border/80 backdrop-blur-xl"
      >
        <SidebarHeader className="mb-3 flex h-20 justify-center border-b px-4 group-data-[collapsible=icon]:px-1.5">
          <Brand />
        </SidebarHeader>
        <SidebarContent>
          <DashboardNav groups={groups} />
        </SidebarContent>
        <SidebarUser name={user.name} email={user.email} role={role} />
      </Sidebar>
      <SidebarInset>
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b bg-bg/80 px-6 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <span className="h-4 w-px bg-border" />
            <DashboardTitle />
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden font-mono text-xs tracking-caps text-text-muted sm:inline">
              HACK HAMSTER / 2026
            </span>
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 p-6 lg:p-10">
          <PageTransition>{children}</PageTransition>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
