import { SearchX } from "lucide-react";
import { EmptyState } from "@/components/portal-ui";

export default function ProjectNotFound() {
  return (
    <div className="py-10">
      <EmptyState
        icon={SearchX}
        title="This project isn’t in the gallery"
        description="It may have been removed or its link may have changed. There are more great ideas to explore."
        href="/gallery"
        action="Back to gallery"
      />
    </div>
  );
}
