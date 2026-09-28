import { cookies } from "next/headers";
import { Scale } from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { EmptyState, PageHeading } from "@/components/portal-ui";
import { PairwiseCompare } from "./PairwiseCompare";

export default async function PairwisePage() {
  const cookieHeader = (await cookies()).toString();
  const user = await api.me(cookieHeader);
  const membership = user.memberships.find(
    (entry) => entry.event === EVENT_SLUG,
  );
  const canCompare =
    membership?.role === "judge" || membership?.role === "admin";

  if (!canCompare) {
    return (
      <>
        <PageHeading
          eyebrow="JUDGING / COMPARISONS"
          title="Pairwise compare"
          description="Two ideas. One considered choice."
        />
        <EmptyState
          icon={Scale}
          title="A space for judges"
          description="Only judges can compare projects. Sign in with your judge account to participate."
          href="/login"
          action="Switch accounts"
        />
      </>
    );
  }
  return <PairwiseCompare />;
}
