"use client";

import { RouteError } from "@/components/route-error";

export default function JudgeProjectError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError message={`Could not load this project: ${error.message}`} reset={reset} />;
}
