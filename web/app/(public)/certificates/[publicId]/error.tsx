"use client";
import { RouteError } from "@/components/route-error";

export default function CertificateError({
  reset,
  retry,
}: {
  error: Error & { digest?: string };
  reset?: () => void;
  retry?: () => void;
}) {
  return (
    <div className="mx-auto max-w-2xl py-10">
      <RouteError
        message="We couldn’t verify this certificate"
        reset={retry ?? reset ?? (() => window.location.reload())}
      />
    </div>
  );
}
