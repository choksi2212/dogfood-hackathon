"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CertificateLookupPage() {
  const router = useRouter();
  const [publicId, setPublicId] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = publicId.trim();
    if (trimmed) router.push(`/certificates/${encodeURIComponent(trimmed)}`);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Verify a certificate</h1>
      <p className="mt-1 max-w-lg text-muted-foreground">
        Certificates are public, HMAC-signed records. Paste a certificate ID to verify
        its signature and see what it attests.
      </p>
      <form className="mt-6 flex max-w-md items-end gap-2" onSubmit={handleSubmit}>
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="public-id">Certificate ID</Label>
          <Input
            id="public-id"
            value={publicId}
            onChange={(e) => setPublicId(e.target.value)}
            placeholder="Certificate ID"
            required
          />
        </div>
        <Button type="submit">Verify</Button>
      </form>
    </div>
  );
}
