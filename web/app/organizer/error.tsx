"use client";

import { ErrorState } from "@/components/StateMessage";

export default function OrganizerError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState>
      <p>Could not load the dashboard: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </ErrorState>
  );
}
