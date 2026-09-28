"use client";
import { RouteError } from "@/components/route-error";

export default function ProjectError({
  reset,
  retry,
}: {
  error: Error & { digest?: string };
  reset?: () => void;
  retry?: () => void;
}) {
  return (
    <RouteError
      message="This project couldn’t be loaded"
      reset={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
