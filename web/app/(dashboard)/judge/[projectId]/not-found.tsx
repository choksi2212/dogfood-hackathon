import { ClipboardCheck } from "lucide-react";
import { EmptyState } from "@/components/portal-ui";

export default function NotFound() {
  return (
    <EmptyState
      icon={ClipboardCheck}
      title="This project isn’t in your batch"
      description="Return to your judging workspace to see the projects assigned to you."
      href="/judge"
      action="Back to your batch"
    />
  );
}
