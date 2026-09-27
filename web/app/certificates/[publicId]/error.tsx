"use client";

import { ErrorState } from "@/components/StateMessage";

export default function CertificateError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState>
      <p>Could not verify this certificate: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </ErrorState>
  );
}
