"use client";

import { RouteError } from "@/components/route-error";

export default function ErrorBoundary({
  retry,
  reset,
}: {
  error: Error & { digest?: string };
  retry?: () => void;
  reset?: () => void;
}) {
  return (
    <RouteError
      message="We couldn’t load comparisons"
      reset={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
