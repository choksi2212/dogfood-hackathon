import { cookies } from "next/headers";
import { Rocket } from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { EmptyState } from "@/components/portal-ui";
import { SubmitForm } from "./SubmitForm";
export default async function SubmitPage() {
  const cookieHeader = (await cookies()).toString();
  const user = await api.me(cookieHeader);
  const membership = user.memberships.find((m) => m.event === EVENT_SLUG);
  if (membership?.role !== "participant" && membership?.role !== "admin") {
    return (
      <EmptyState
        icon={Rocket}
        title="Participants only"
        description="Switch to a participant account to submit your project. Your organizer can help you join the event."
        href="/login"
        action="Switch accounts"
      />
    );
  }
  return (
    <SubmitForm draftKey={`ledger:${EVENT_SLUG}:${user.id}:project-draft`} />
  );
}
