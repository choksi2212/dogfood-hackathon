"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { InputField, SelectField, TextareaField } from "@/components/Field";
import { Button } from "@/components/Button";
import styles from "./submit.module.css";

type Status = "idle" | "loading" | "success" | "error";
type AuthState = "checking" | "anon" | "authed";

const KNOWN_TRACKS = [
  { slug: "main", label: "Main" },
  { slug: "wildcard", label: "Wildcard" },
];

export default function SubmitPage() {
  const router = useRouter();
  const [auth, setAuth] = useState<AuthState>("checking");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    tagline: "",
    description: "",
    repo_url: "",
    live_url: "",
    demo_video_url: "",
    track_slug: KNOWN_TRACKS[0].slug,
  });

  // Auth gate — anonymous visitors see "sign in to submit" instead of
  // an empty form that will 401 on click. The /api/me probe is cheap
  // (one SELECT on the session table) and idempotent.
  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then(() => {
        if (!cancelled) setAuth("authed");
      })
      .catch(() => {
        if (!cancelled) setAuth("anon");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage(null);
    try {
      const created = await api.submit(form);
      // Don't leave the user on a static "received" page — they want
      // to see their submission in the gallery right away.
      router.push(`/gallery/${created.id}`);
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof ApiError ? err.message : "Something went wrong.",
      );
    }
  }

  if (auth === "checking") {
    return <p className={styles.muted}>Checking your session…</p>;
  }

  if (auth === "anon") {
    return (
      <div className={styles.gate}>
        <h1 className={styles.gateTitle}>Sign in to submit</h1>
        <p className={styles.gateBody}>
          Submissions are tied to your account so the organizer can reach
          you if there&apos;s a question about your entry.
        </p>
        <div className={styles.gateActions}>
          <Link href="/login">
            <Button variant="primary">Sign in</Button>
          </Link>
          <Link href="/register">
            <Button variant="secondary">Create an account</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Submit your project"
        description="Tell judges what you built — you can edit this until submissions close."
      />
      <form className={styles.form} onSubmit={handleSubmit}>
        <InputField
          label="Project name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          maxLength={80}
          required
        />
        <InputField
          label="Tagline"
          value={form.tagline}
          onChange={(e) => setForm({ ...form, tagline: e.target.value })}
          maxLength={140}
          placeholder="One sentence — what's the hook?"
        />
        <TextareaField
          label="Description"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          rows={6}
          maxLength={8000}
        />
        <SelectField
          label="Track"
          value={form.track_slug}
          onChange={(e) => setForm({ ...form, track_slug: e.target.value })}
          required
        >
          {KNOWN_TRACKS.map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.label}
            </option>
          ))}
        </SelectField>
        <InputField
          label="Source repo (optional)"
          type="url"
          value={form.repo_url}
          onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
          placeholder="https://github.com/team/project"
        />
        <InputField
          label="Live site (optional)"
          type="url"
          value={form.live_url}
          onChange={(e) => setForm({ ...form, live_url: e.target.value })}
          placeholder="https://example.com"
        />
        <InputField
          label="Demo video (optional)"
          type="url"
          value={form.demo_video_url}
          onChange={(e) => setForm({ ...form, demo_video_url: e.target.value })}
          placeholder="https://youtu.be/…"
        />
        <Button type="submit" loading={status === "loading"} className={styles.submitButton}>
          Submit
        </Button>
        {status === "error" && errorMessage && (
          <ErrorState>{errorMessage}</ErrorState>
        )}
      </form>
    </div>
  );
}
