"use client";

import { RouteError } from "@/components/route-error";

export default function CertificateError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteError
      message={`Could not verify this certificate: ${error.message}`}
      reset={reset}
    />
  );
}
