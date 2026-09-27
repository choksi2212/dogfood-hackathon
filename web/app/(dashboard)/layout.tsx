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
  const isJudge = role === "judge";
  const isOrganizer = role === "organizer" || role === "admin";

  const groups: NavGroup[] = [
    {
      label: "Participant",
      items: [
        { href: "/submit", label: "Submit", icon: "rocket" },
        { href: "/vote", label: "Vote", icon: "thumbsUp" },
      ],
    },
  ];
  if (isJudge) {
    groups.push({
      label: "Judge",
      items: [
        { href: "/judge", label: "My batch", icon: "listChecks" },
        { href: "/pairwise", label: "Pairwise compare", icon: "scale" },
        { href: "/pairwise/ranking", label: "Pairwise ranking", icon: "barChart" },
      ],
    });
  }
  if (isOrganizer) {
    groups.push({
      label: "Organizer",
      items: [
        { href: "/organizer", label: "Dashboard", icon: "layoutDashboard" },
        { href: "/organizer/results", label: "Results & audit", icon: "clipboardList" },
      ],
    });
  }

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <span className="px-2 py-1 text-sm font-bold tracking-tight">Dogfood Portal</span>
        </SidebarHeader>
        <SidebarContent>
          <DashboardNav groups={groups} />
        </SidebarContent>
        <SidebarUser name={user.name} email={user.email} role={role} />
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 items-center justify-between border-b px-4">
          <SidebarTrigger />
          <ThemeToggle />
        </header>
        <main className="flex-1 p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
