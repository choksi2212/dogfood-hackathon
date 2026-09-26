"use client";

import { ErrorState } from "@/components/StateMessage";

export default function JudgeError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState>
      <p>Could not load your batch: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </ErrorState>
  );
}
