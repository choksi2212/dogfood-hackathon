"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { api } from "@/lib/api/client";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  SidebarFooter,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar";

export function SidebarUser({
  name,
  email,
  role,
}: {
  name: string;
  email: string;
  role: string;
}) {
  const router = useRouter();

  async function handleLogout() {
    await api.logout();
    router.push("/login");
    router.refresh();
  }

  return (
    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem className="flex items-center gap-2 px-2 py-1.5">
          <Avatar className="size-8">
            <AvatarFallback>{name.slice(0, 1).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-sm font-medium">{name}</span>
            <span className="truncate text-xs text-muted-foreground">{email}</span>
          </div>
          <Badge variant="secondary" className="capitalize">
            {role}
          </Badge>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton onClick={handleLogout}>
            <LogOut />
            <span>Log out</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarFooter>
  );
}
