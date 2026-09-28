"use client";
import { RouteError } from "@/components/route-error";
export default function WidgetError({
  reset,
  retry,
}: {
  error: Error & { digest?: string };
  reset?: () => void;
  retry?: () => void;
}) {
  return (
    <RouteError
      message="We couldn’t load the widget"
      reset={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
