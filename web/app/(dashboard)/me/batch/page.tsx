import { redirect } from "next/navigation";

// /me/batch is the documented alias of the judge batch screen — the
// REST path is /api/events/<slug>/me/batch (PRD S-020 mounts the
// screen at /judge). Redirect so the canonical screen renders with its
// own URL; the (dashboard) layout still sends unauthenticated visitors
// to /login first, so the path never 404s.
export default function MeBatchPage() {
  redirect("/judge");
}
