"use client";

import { RouteError } from "@/components/route-error";

export default function GalleryError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError message={`Could not load the gallery: ${error.message}`} reset={reset} />;
}
