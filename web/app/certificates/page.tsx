"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
      <h1>Verify a certificate</h1>
      <p className={styles.lede}>
        Certificates are public, HMAC-signed records. Paste a certificate ID
        to verify its signature and see what it attests.
      </p>
      <form className={styles.form} onSubmit={handleSubmit}>
        <input
          className={styles.input}
          value={publicId}
          onChange={(e) => setPublicId(e.target.value)}
          placeholder="Certificate ID"
          required
        />
        <button className={styles.button} type="submit">
          Verify
        </button>
      </form>
    </div>
  );
}
