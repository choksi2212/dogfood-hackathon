import { Fingerprint, LockKeyhole, ShieldCheck } from "lucide-react";
import { CertificateForm } from "./certificate-form";

export default function CertificateLookupPage() {
  return (
    <div className="mx-auto max-w-2xl py-5 sm:py-10">
      <div className="relative overflow-hidden rounded-3xl border border-border bg-bg-elevated px-7 py-10 shadow-card sm:px-12 sm:py-12">
        <div className="relative">
          <div className="mb-7 flex size-16 items-center justify-center rounded-2xl border border-accent/20 bg-accent-dim text-accent">
            <ShieldCheck className="size-8" strokeWidth={1.5} />
          </div>
          <p className="eyebrow">TRUST, YOU CAN VERIFY</p>
          <h1 className="mt-4 font-display text-3xl leading-tight font-medium tracking-display sm:text-4xl">
            A milestone.
            <br />
            An authentic record.
          </h1>
          <p className="mt-5 max-w-md text-sm leading-relaxed text-text-secondary">
            Every Ledger certificate carries a signed record. Enter its public
            ID to confirm it’s authentic and see what it recognizes.
          </p>
          <div className="mt-9">
            <CertificateForm />
          </div>
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-6 text-xs text-text-muted">
            <span className="flex items-center gap-2">
              <LockKeyhole className="size-3.5 text-accent" />
              Signed at issuance
            </span>
            <span className="flex items-center gap-2">
              <Fingerprint className="size-3.5 text-accent" />
              Verified against the original
            </span>
          </div>
        </div>
      </div>
      <p className="mt-5 text-center text-xs leading-relaxed text-text-muted">
        Verification is public. You don’t need an account.
      </p>
    </div>
  );
}
