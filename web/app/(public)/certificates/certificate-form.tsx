"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, LoaderCircle, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function CertificateForm({ initialId = "" }: { initialId?: string }) {
  const router = useRouter();
  const [publicId, setPublicId] = useState(initialId);
  const [pending, startTransition] = useTransition();
  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const id = publicId.trim();
    if (id)
      startTransition(() => {
        router.push(`/certificates/${encodeURIComponent(id)}`);
        router.refresh();
      });
  }
  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Label htmlFor="public-id">Certificate public ID</Label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-3.5 left-3.5 size-4 text-text-muted"
            aria-hidden="true"
          />
          <Input
            id="public-id"
            value={publicId}
            onChange={(e) => setPublicId(e.target.value)}
            placeholder="Paste the ID from your certificate"
            autoCapitalize="none"
            spellCheck={false}
            required
            disabled={pending}
            className="h-12 rounded-xl border-border bg-bg-overlay pl-10 font-mono text-xs"
          />
        </div>
        <Button type="submit" size="lg" disabled={pending || !publicId.trim()}>
          {pending ? (
            <>
              <LoaderCircle className="size-4 motion-safe:animate-spin" />
              Verifying…
            </>
          ) : (
            <>
              Verify
              <ArrowRight className="size-4" />
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
