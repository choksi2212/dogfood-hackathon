import Link from "next/link";
import {
  Award,
  CheckCircle2,
  FileQuestion,
  Gavel,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { ClientDate } from "@/components/client-date";
import type {
  CertificateResponse,
  JudgeRecordResponse,
} from "@/lib/api/types";
import { CertificateForm } from "../certificate-form";

type Result =
  | { kind: "ok"; cert: CertificateResponse }
  | { kind: "judge"; record: JudgeRecordResponse }
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
    if (err instanceof ApiError && err.code === "signature_invalid")
      result = { kind: "tampered" };
    else if (err instanceof ApiError && err.status === 404) {
      // Judge participation records are public, signed records too, but
      // they are served by /api/records/judge/<id>, not
      // /api/certificates/<id> — a public ID that misses the certificate
      // store may still verify here. (The judge-record endpoint returns
      // no email, so nothing below ever displays one.)
      try {
        result = { kind: "judge", record: await api.judgeRecord(publicId) };
      } catch (fallbackErr) {
        if (
          fallbackErr instanceof ApiError &&
          fallbackErr.status === 404
        )
          result = { kind: "not_found" };
        else throw fallbackErr;
      }
    } else throw err;
  }

  if (result.kind === "judge") {
    const { record } = result;
    const stats = record.signed_payload;
    return (
      <div className="mx-auto max-w-3xl py-5 sm:py-10">
        <section className="relative overflow-hidden rounded-3xl border border-border bg-bg-elevated p-7 shadow-card sm:p-10">
          <header className="relative flex flex-wrap items-start justify-between gap-5">
            <div>
              <div className="mb-6 flex size-16 items-center justify-center rounded-2xl border border-success/20 bg-success-dim text-success">
                <ShieldCheck className="size-8" strokeWidth={1.5} />
              </div>
              <p className="eyebrow text-success">AUTHENTICITY CONFIRMED</p>
              <h1 className="mt-4 text-3xl font-medium tracking-display sm:text-4xl">
                Judge participation record.
              </h1>
            </div>
            <Gavel
              className="mt-1 hidden size-12 text-accent-2 sm:block"
              strokeWidth={1}
            />
          </header>
          <Badge className="mt-6 h-8 gap-2 border-success/20 bg-success-dim px-3 text-success">
            <CheckCircle2 className="size-4" />
            Signature valid
          </Badge>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            This judge participation record matches its original signed
            record. Its contents have not been altered since issuance.
          </p>
          <dl className="mt-8 divide-y divide-border rounded-2xl border border-border bg-bg px-5 sm:px-6">
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Record ID</dt>
              <dd className="font-mono text-xs break-all">{record.public_id}</dd>
            </div>
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Judge</dt>
              <dd className="font-mono text-xs">{record.judge}</dd>
            </div>
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Event</dt>
              <dd className="font-mono text-xs">
                {stats.event}{" "}
                <span className="text-text-muted">({stats.event_slug})</span>
              </dd>
            </div>
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Assignments</dt>
              <dd className="font-mono text-xs">{stats.assignments}</dd>
            </div>
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Scores submitted</dt>
              <dd className="font-mono text-xs">{stats.scores_submitted}</dd>
            </div>
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Issued</dt>
              <dd className="font-mono text-xs">
                <ClientDate iso={record.issued_at} />
              </dd>
            </div>
            <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
              <dt className="text-xs text-text-muted">Signature algorithm</dt>
              <dd className="font-mono text-xs">
                {record.signature_algorithm}
              </dd>
            </div>
          </dl>
          <details className="mt-6 rounded-xl border border-border">
            <summary className="cursor-pointer px-5 py-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-accent">
              View signed record
            </summary>
            <pre className="max-h-80 overflow-auto border-t border-border bg-bg p-5 font-mono text-xs leading-relaxed text-text-secondary">
              {JSON.stringify(record.signed_payload, null, 2)}
            </pre>
          </details>
          <div className="mt-8 border-t border-border pt-7">
            <h2 className="mb-4 text-sm font-medium">
              Verify another record
            </h2>
            <CertificateForm />
          </div>
        </section>
      </div>
    );
  }

  if (result.kind !== "ok") {
    const tampered = result.kind === "tampered";
    const Icon = tampered ? ShieldX : FileQuestion;
    return (
      <div className="mx-auto max-w-2xl py-5 sm:py-10">
        <section className="rounded-3xl border border-border bg-bg-elevated p-7 shadow-card sm:p-10">
          <div className="mb-6 flex size-16 items-center justify-center rounded-2xl bg-error-dim text-error">
            <Icon className="size-8" strokeWidth={1.5} />
          </div>
          <p className="eyebrow text-error">VERIFICATION RESULT</p>
          <h1 className="mt-4 text-3xl font-medium tracking-display">
            {tampered
              ? "This record has been altered."
              : "No matching record."}
          </h1>
          <Badge variant="destructive" className="mt-5 h-7 px-3">
            {tampered
              ? "Signature invalid · tampered"
              : "Not found"}
          </Badge>
          <p className="mt-5 text-sm leading-relaxed text-text-secondary">
            {tampered
              ? "The signature doesn’t match the record’s contents. Its authenticity cannot be confirmed. Contact the event organizer for an original copy."
              : "We couldn’t find a certificate or judge participation record with this public ID. Check the ID on your record and try again."}
          </p>
          <p className="mt-5 rounded-xl border border-border bg-bg p-4 font-mono text-xs break-all text-text-muted">
            {publicId}
          </p>
          <div className="mt-8 border-t border-border pt-7">
            <CertificateForm initialId={publicId} />
          </div>
        </section>
      </div>
    );
  }
  const { cert } = result;
  return (
    <div className="mx-auto max-w-3xl py-5 sm:py-10">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-bg-elevated p-7 shadow-card sm:p-10">
        <header className="relative flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="mb-6 flex size-16 items-center justify-center rounded-2xl border border-success/20 bg-success-dim text-success">
              <ShieldCheck className="size-8" strokeWidth={1.5} />
            </div>
            <p className="eyebrow text-success">AUTHENTICITY CONFIRMED</p>
            <h1 className="mt-4 text-3xl font-medium tracking-display sm:text-4xl">
              Certificate verified.
            </h1>
          </div>
          <Award
            className="mt-1 hidden size-12 text-accent-2 sm:block"
            strokeWidth={1}
          />
        </header>
        <Badge className="mt-6 h-8 gap-2 border-success/20 bg-success-dim px-3 text-success">
          <CheckCircle2 className="size-4" />
          Signature valid
        </Badge>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          This certificate matches its original signed record. Its contents have
          not been altered since issuance.
        </p>
        <dl className="mt-8 divide-y divide-border rounded-2xl border border-border bg-bg px-5 sm:px-6">
          <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
            <dt className="text-xs text-text-muted">Certificate ID</dt>
            <dd className="font-mono text-xs break-all">{cert.public_id}</dd>
          </div>
          <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
            <dt className="text-xs text-text-muted">Project</dt>
            <dd>
              <Link
                href={`/gallery/${encodeURIComponent(cert.submission_id)}`}
                className="font-mono text-xs break-all text-accent hover:text-accent-hover"
              >
                {cert.submission_id}
              </Link>
            </dd>
          </div>
          <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
            <dt className="text-xs text-text-muted">Issued</dt>
            <dd className="font-mono text-xs">
              <ClientDate iso={cert.issued_at} />
            </dd>
          </div>
          <div className="grid gap-2 py-5 sm:grid-cols-[150px_1fr]">
            <dt className="text-xs text-text-muted">Signature algorithm</dt>
            <dd className="font-mono text-xs">{cert.signature_algorithm}</dd>
          </div>
        </dl>
        <details className="mt-6 rounded-xl border border-border">
          <summary className="cursor-pointer px-5 py-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-accent">
            View signed record
          </summary>
          <pre className="max-h-80 overflow-auto border-t border-border bg-bg p-5 font-mono text-xs leading-relaxed text-text-secondary">
            {JSON.stringify(cert.signed_payload, null, 2)}
          </pre>
        </details>
        <div className="mt-8 border-t border-border pt-7">
          <h2 className="mb-4 text-sm font-medium">
            Verify another certificate
          </h2>
          <CertificateForm />
        </div>
      </section>
    </div>
  );
}
