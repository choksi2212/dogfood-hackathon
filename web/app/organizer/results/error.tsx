"use client";

import { ErrorState } from "@/components/StateMessage";

export default function ResultsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState>
      <p>Could not load results or the audit log: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </ErrorState>
  );
}
