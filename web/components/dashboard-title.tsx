"use client";
import { usePathname } from "next/navigation";

export function DashboardTitle() {
  const path = usePathname();
  const title = path.startsWith("/judge/")
    ? "Review workspace"
    : ((
        {
          "/submit": "Your submission",
          "/vote": "Community voting",
          "/judge": "Judge workspace",
          "/organizer": "Event overview",
          "/organizer/results": "Results & audit",
          "/pairwise": "Pairwise compare",
          "/pairwise/ranking": "Pairwise ranking",
        } as Record<string, string>
      )[path] ?? "Workspace");
  return <span className="text-sm font-medium">{title}</span>;
}
