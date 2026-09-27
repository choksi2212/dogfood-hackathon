"use client";

import { RouteError } from "@/components/route-error";

export default function JudgeError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError message={`Could not load your batch: ${error.message}`} reset={reset} />;
}
