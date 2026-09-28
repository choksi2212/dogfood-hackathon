"use client";
import { RouteError } from "@/components/route-error";
export default function DashboardError({
  retry,
  reset,
}: {
  error: Error & { digest?: string };
  retry?: () => void;
  reset?: () => void;
}) {
  return (
    <RouteError
      message="Could not load your workspace"
      reset={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
