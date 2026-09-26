"use client";

import { ErrorState } from "@/components/StateMessage";

export default function GalleryError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState>
      <p>Could not load the gallery: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </ErrorState>
  );
}
