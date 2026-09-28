import { cookies } from "next/headers";
import { AlertCircle } from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PairwiseCompare } from "./PairwiseCompare";

export default async function PairwisePage() {
  const cookieHeader = (await cookies()).toString();
  // The layout already guarantees a signed-in session — this just
  // decides whether to render the comparison controls at all. Mirrors
  // /api/events/<slug>/pairwise/ballots' own IsJudge check (judge or
  // admin) so a participant never sees a "vote" they can't cast instead
  // of finding out only after clicking it.
  const user = await api.me(cookieHeader);
  const membership = user.memberships.find((m) => m.event === EVENT_SLUG);
  const canCompare = membership?.role === "judge" || membership?.role === "admin";

  if (!canCompare) {
    return (
      <Alert>
        <AlertCircle className="size-4" />
        <AlertTitle>Judges only</AlertTitle>
        <AlertDescription>
          Only judges can compare projects. Switch accounts to participate.
        </AlertDescription>
      </Alert>
    );
  }

  return <PairwiseCompare />;
}
