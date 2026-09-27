"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
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
          you if there's a question about your entry.
        </p>
        <div className={styles.gateActions}>
          <Link href="/login" className={styles.gatePrimary}>
            Sign in
          </Link>
          <Link href="/register" className={styles.gateSecondary}>
            Create an account
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Submit your project</h1>
      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.field}>
          Project name
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            maxLength={80}
            required
          />
        </label>
        <label className={styles.field}>
          Tagline
          <input
            value={form.tagline}
            onChange={(e) => setForm({ ...form, tagline: e.target.value })}
            maxLength={140}
            placeholder="One sentence — what's the hook?"
          />
        </label>
        <label className={styles.field}>
          Description
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={6}
            maxLength={8000}
          />
        </label>
        <label className={styles.field}>
          Track
          <select
            value={form.track_slug}
            onChange={(e) => setForm({ ...form, track_slug: e.target.value })}
            required
          >
            {KNOWN_TRACKS.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Source repo (optional)
          <input
            type="url"
            value={form.repo_url}
            onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
            placeholder="https://github.com/team/project"
          />
        </label>
        <label className={styles.field}>
          Live site (optional)
          <input
            type="url"
            value={form.live_url}
            onChange={(e) => setForm({ ...form, live_url: e.target.value })}
            placeholder="https://example.com"
          />
        </label>
        <label className={styles.field}>
          Demo video (optional)
          <input
            type="url"
            value={form.demo_video_url}
            onChange={(e) => setForm({ ...form, demo_video_url: e.target.value })}
            placeholder="https://youtu.be/…"
          />
        </label>
        <button
          className={styles.submitButton}
          type="submit"
          disabled={status === "loading"}
        >
          {status === "loading" ? "Submitting..." : "Submit"}
        </button>
        {status === "error" && errorMessage && (
          <ErrorState>{errorMessage}</ErrorState>
        )}
      </form>
    </div>
  );
}
