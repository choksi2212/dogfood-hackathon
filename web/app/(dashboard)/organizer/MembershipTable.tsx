"use client";

import { useMemo, useState } from "react";
import { Search, Users, X } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { Membership } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { EmptyState } from "@/components/portal-ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const roleColors = {
  judge: "border-accent/25 bg-accent-dim text-accent",
  organizer: "border-accent-2/25 bg-accent-2/10 text-accent-2",
  participant: "border-success/25 bg-success-dim text-success",
  admin: "border-info/25 bg-info/10 text-blue-700 dark:text-blue-400",
};

export function MembershipTable({
  memberships,
}: {
  memberships: Membership[];
}) {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("all");
  const reducedMotion = useReducedMotion();
  const filtered = useMemo(
    () =>
      memberships.filter(
        (member) =>
          (role === "all" || member.role === role) &&
          `${member.user_name} ${member.user_email}`
            .toLowerCase()
            .includes(search.trim().toLowerCase()),
      ),
    [memberships, role, search],
  );
  return (
    <section aria-labelledby="membership-title">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">YOUR PEOPLE</p>
          <h2
            id="membership-title"
            className="text-2xl font-medium tracking-tight"
          >
            Event members{" "}
            <span className="ml-2 align-middle font-mono text-sm text-text-muted">
              {memberships.length}
            </span>
          </h2>
          <p className="mt-2 text-sm text-text-secondary">
            The builders, judges, and organizers making this event happen.
          </p>
        </div>
      </div>
      <div className="surface overflow-hidden rounded-2xl">
        <div className="flex flex-wrap items-center gap-3 border-b p-4 sm:p-5">
          <div className="relative min-w-48 flex-1 sm:max-w-sm">
            <Label htmlFor="member-search" className="sr-only">
              Search members by name or email
            </Label>
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted" />
            <Input
              id="member-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name or email…"
              className="bg-bg-overlay pl-9"
            />
          </div>
          <Label htmlFor="member-role" className="sr-only">
            Filter members by role
          </Label>
          <Select
            value={role}
            onValueChange={(value) => {
              if (value !== null) setRole(value);
            }}
          >
            <SelectTrigger id="member-role" className="w-40 bg-bg-overlay">
              <SelectValue placeholder="All roles" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All roles</SelectItem>
              <SelectItem value="organizer">Organizers</SelectItem>
              <SelectItem value="judge">Judges</SelectItem>
              <SelectItem value="participant">Participants</SelectItem>
              <SelectItem value="admin">Admins</SelectItem>
            </SelectContent>
          </Select>
          <span
            className="ml-auto font-mono text-xs text-text-muted"
            aria-live="polite"
          >
            {filtered.length} shown
          </span>
        </div>
        {filtered.length === 0 ? (
          <div className="p-5">
            <EmptyState
              icon={Users}
              title={
                memberships.length
                  ? "No matching members"
                  : "Your team starts here"
              }
              description={
                memberships.length
                  ? "Try a different name, email, or role."
                  : "Invite judges below to build your review panel."
              }
            />
            {memberships.length > 0 && (
              <div className="mt-3 text-center">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSearch("");
                    setRole("all");
                  }}
                >
                  <X className="size-4" />
                  Clear filters
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="[&_[data-slot=table-container]]:max-h-[440px] [&_[data-slot=table-container]]:overflow-auto">
            <Table className="min-w-[580px]">
              <TableHeader className="sticky top-0 z-10 bg-bg-elevated">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-12 pl-6 text-xs">Member</TableHead>
                  <TableHead className="text-xs">Email address</TableHead>
                  <TableHead className="pr-6 text-right text-xs">
                    Role
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((member, index) => (
                  <motion.tr
                    key={member.id}
                    initial={reducedMotion ? false : { opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.2,
                      delay: Math.min(index, 5) * 0.05,
                    }}
                    className={cn(
                      "border-b last:border-b-0 hover:bg-bg-overlay",
                      index % 2 ? "bg-bg-elevated" : "bg-bg",
                    )}
                  >
                    <TableCell className="py-4 pl-6">
                      <div className="flex items-center gap-3">
                        <span
                          aria-hidden="true"
                          className="flex size-9 shrink-0 items-center justify-center rounded-full border bg-bg-overlay text-xs font-medium text-text-secondary"
                        >
                          {(member.user_name || member.user_email)
                            .split(/\s+/)
                            .slice(0, 2)
                            .map((name) => name[0])
                            .join("")
                            .toUpperCase()}
                        </span>
                        <span className="font-medium">
                          {member.user_name || "Unnamed member"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-text-secondary">
                      {member.user_email}
                    </TableCell>
                    <TableCell className="pr-6 text-right">
                      <Badge
                        variant="outline"
                        className={cn(
                          "rounded-full px-3 py-1 text-xs capitalize",
                          roleColors[member.role],
                        )}
                      >
                        {member.role}
                      </Badge>
                    </TableCell>
                  </motion.tr>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </section>
  );
}
