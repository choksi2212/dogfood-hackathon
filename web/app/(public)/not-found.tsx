import { SearchX } from "lucide-react";
import { EmptyState } from "@/components/portal-ui";
export default function NotFound() {
  return (
    <EmptyState
      icon={SearchX}
      title="This project isn’t here"
      description="It may have moved, or the link may be incomplete. There’s plenty more to discover in the gallery."
      href="/gallery"
      action="Explore the gallery"
    />
  );
}
