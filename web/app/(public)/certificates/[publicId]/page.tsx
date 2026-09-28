import { CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ClientDate } from "@/components/client-date";
import type { CertificateResponse } from "@/lib/api/types";

type Result =
  | { kind: "ok"; cert: CertificateResponse }
  | { kind: "not_found" }
  | { kind: "tampered" };

export default async function CertificatePage({
  params,
}: {
  params: Promise<{ publicId: string }>;
}) {
  const { publicId } = await params;

  let result: Result;
  try {
    result = { kind: "ok", cert: await api.certificate(publicId) };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      result = { kind: "not_found" };
    } else if (err instanceof ApiError && err.code === "signature_invalid") {
      result = { kind: "tampered" };
    } else {
      throw err;
    }
  }

  if (result.kind === "not_found") {
    return (
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Certificate not found</h1>
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>
            No certificate exists with ID &quot;{publicId}&quot;.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (result.kind === "tampered") {
    return (
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Certificate tampered</h1>
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>
            This certificate&apos;s signature does not match its payload — it may have
            been altered after issuance.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const { cert } = result;

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Certificate verified</h1>
      <Badge className="mt-3 gap-1 bg-success text-success-foreground">
        <CheckCircle2 className="size-3.5" />
        Signature valid ({cert.signature_algorithm})
      </Badge>
      <dl className="mt-4 grid max-w-md grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-sm text-muted-foreground">Certificate ID</dt>
        <dd className="tabular-nums">{cert.public_id}</dd>
        <dt className="text-sm text-muted-foreground">Submission</dt>
        <dd className="tabular-nums">{cert.submission_id}</dd>
        <dt className="text-sm text-muted-foreground">Issued</dt>
        <dd className="tabular-nums">
          <ClientDate iso={cert.issued_at} />
        </dd>
      </dl>
      <h2 className="mt-6 mb-3 text-lg font-semibold">Signed payload</h2>
      <pre className="max-w-md overflow-x-auto rounded-lg border bg-muted p-3 text-sm">
        {JSON.stringify(cert.signed_payload, null, 2)}
      </pre>
    </div>
  );
}
