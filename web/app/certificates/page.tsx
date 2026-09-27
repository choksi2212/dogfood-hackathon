"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { InputField } from "@/components/Field";
import { Button } from "@/components/Button";
import styles from "./certificates.module.css";

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
      <PageHeader
        title="Verify a certificate"
        description="Certificates are public, HMAC-signed records. Paste a certificate ID to verify its signature and see what it attests."
      />
      <form className={styles.form} onSubmit={handleSubmit}>
        <InputField
          label="Certificate ID"
          value={publicId}
          onChange={(e) => setPublicId(e.target.value)}
          placeholder="Certificate ID"
          required
          className={styles.input}
        />
        <Button type="submit">Verify</Button>
      </form>
    </div>
  );
}
