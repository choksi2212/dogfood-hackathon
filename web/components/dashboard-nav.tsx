"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  Rocket,
  Scale,
  ThumbsUp,
  LayoutGrid,
  type LucideIcon,
} from "lucide-react";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar";

// Server Components can't pass component/function references as props to
// Client Components (only plain serializable data crosses that boundary),
// so the layout sends icon *keys* and this map resolves them locally.
const ICONS = {
  gallery: LayoutGrid,
  rocket: Rocket,
  thumbsUp: ThumbsUp,
  listChecks: ListChecks,
  scale: Scale,
  barChart: BarChart3,
  layoutDashboard: LayoutDashboard,
  clipboardList: ClipboardList,
} satisfies Record<string, LucideIcon>;

export type IconKey = keyof typeof ICONS;
export type NavItem = { href: string; label: string; icon: IconKey };
export type NavGroup = { label: string; items: NavItem[] };

// A route like /pairwise/ranking starts with both "/pairwise/" and
// "/pairwise/ranking" — naive prefix matching would light up both nav
// items. Only the href that's the longest (most specific) match wins.
function findActiveHref(pathname: string, hrefs: string[]): string | undefined {
  const matches = hrefs.filter(
    (href) => pathname === href || pathname.startsWith(`${href}/`),
  );
  return matches.sort((a, b) => b.length - a.length)[0];
}

export function DashboardNav({ groups }: { groups: NavGroup[] }) {
  const pathname = usePathname();
  const activeHref = findActiveHref(
    pathname,
    groups.flatMap((g) => g.items.map((i) => i.href)),
  );

  return (
    <>
      {groups.map((group) => (
        <SidebarGroup key={group.label}>
          <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {group.items.map((item) => {
                const Icon = ICONS[item.icon];
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      isActive={item.href === activeHref}
                      render={
                        <Link href={item.href}>
                          <Icon />
                          <span>{item.label}</span>
                        </Link>
                      }
                    />
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  );
}
