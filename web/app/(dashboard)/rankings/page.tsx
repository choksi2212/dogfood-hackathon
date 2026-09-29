import { redirect } from "next/navigation";

// /rankings is the documented alias of the pairwise ranking screen —
// the Bradley–Terry leaderboard lives at /pairwise/ranking (the CSV a
// full organizer export produces is served from the same fit). Redirect
// so the canonical screen renders with its own URL; the (dashboard)
// layout still sends unauthenticated visitors to /login first, so the
// path never 404s.
export default function RankingsPage() {
  redirect("/pairwise/ranking");
}
