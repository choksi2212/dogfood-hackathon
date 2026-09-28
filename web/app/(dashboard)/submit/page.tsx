import { cookies } from "next/headers";
import { AlertCircle } from "lucide-react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { SubmitForm } from "./SubmitForm";

export default async function SubmitPage() {
  const cookieHeader = (await cookies()).toString();
  // POST .../submit is IsParticipant-gated — check up front instead of
  // rendering a fully-usable form for a judge/organizer that always
  // 403s on click. Same fix as #9 (/pairwise) applied here.
  const user = await api.me(cookieHeader);
  const membership = user.memberships.find((m) => m.event === EVENT_SLUG);
  const canSubmit = membership?.role === "participant" || membership?.role === "admin";

  if (!canSubmit) {
    return (
      <Alert>
        <AlertCircle className="size-4" />
        <AlertTitle>Participants only</AlertTitle>
        <AlertDescription>
          Only participants can submit a project. Switch accounts to participate.
        </AlertDescription>
      </Alert>
    );
  }

  return <SubmitForm />;
}
