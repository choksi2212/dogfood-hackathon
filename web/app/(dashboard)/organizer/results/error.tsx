"use client";

import { RouteError } from "@/components/route-error";

export default function ResultsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteError
      message={`Could not load results or the audit log: ${error.message}`}
      reset={reset}
    />
  );
}
