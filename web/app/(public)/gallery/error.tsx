"use client";
import { RouteError } from "@/components/route-error";
export default function GalleryError({
  retry,
  reset,
}: {
  error: Error & { digest?: string };
  retry?: () => void;
  reset?: () => void;
}) {
  return (
    <RouteError
      message="Could not load the gallery"
      reset={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
