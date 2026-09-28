"use client";
import { RouteError } from "@/components/route-error";
export default function MarketingError({
  retry,
  reset,
}: {
  error: Error & { digest?: string };
  retry?: () => void;
  reset?: () => void;
}) {
  return (
    <div className="container-shell py-20">
      <RouteError
        message="Could not load this page"
        reset={retry ?? reset ?? (() => window.location.reload())}
      />
    </div>
  );
}
