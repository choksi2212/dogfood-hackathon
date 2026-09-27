import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/Badge";
import styles from "./certificate.module.css";

export default async function CertificatePage({
  params,
}: {
  params: Promise<{ publicId: string }>;
}) {
  const { publicId } = await params;

  try {
    const cert = await api.certificate(publicId);
    return (
      <div>
        <PageHeader title="Certificate verified" />
        <Badge tone="success" className={styles.badge}>
          ✓ Signature valid ({cert.signature_algorithm})
        </Badge>
        <dl className={styles.details}>
          <dt>Certificate ID</dt>
          <dd>{cert.public_id}</dd>
          <dt>Submission</dt>
          <dd>{cert.submission_id}</dd>
          <dt>Issued</dt>
          <dd>{new Date(cert.issued_at).toLocaleString()}</dd>
        </dl>
        <h2 className={styles.sectionTitle}>Signed payload</h2>
        <pre className={styles.payload}>
          {JSON.stringify(cert.signed_payload, null, 2)}
        </pre>
      </div>
    );
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return (
        <div>
          <PageHeader title="Certificate not found" />
          <ErrorState>No certificate exists with ID &quot;{publicId}&quot;.</ErrorState>
        </div>
      );
    }
    if (err instanceof ApiError && err.code === "signature_invalid") {
      return (
        <div>
          <PageHeader title="Certificate tampered" />
          <ErrorState>
            This certificate&apos;s signature does not match its payload —
            it may have been altered after issuance.
          </ErrorState>
        </div>
      );
    }
    throw err;
  }
}
