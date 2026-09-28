"use client";

import { RouteError } from "@/components/route-error";

export default function ResultsError({
  retry,
  reset,
}: {
  error: Error & { digest?: string };
  retry?: () => void;
  reset?: () => void;
}) {
  return (
    <RouteError
      message="Could not load results or the audit log"
      reset={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
