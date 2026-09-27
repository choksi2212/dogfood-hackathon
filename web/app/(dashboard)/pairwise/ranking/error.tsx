"use client";

import { RouteError } from "@/components/route-error";

export default function RankingError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError message={`Could not load the ranking: ${error.message}`} reset={reset} />;
}
