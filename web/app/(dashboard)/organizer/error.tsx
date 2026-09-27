"use client";

import { RouteError } from "@/components/route-error";

export default function OrganizerError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError message={`Could not load the dashboard: ${error.message}`} reset={reset} />;
}
