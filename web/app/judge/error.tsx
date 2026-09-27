"use client";

import { ErrorState } from "@/components/StateMessage";
import { Button } from "@/components/Button";

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
      <Button variant="secondary" onClick={reset}>
        Try again
      </Button>
    </ErrorState>
  );
}
