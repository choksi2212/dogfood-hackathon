"use client";

import { ErrorState } from "@/components/StateMessage";

export default function ScoreError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState>
      <p>Could not load this project: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </ErrorState>
  );
}
