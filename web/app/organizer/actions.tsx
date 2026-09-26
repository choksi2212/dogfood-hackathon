"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import type {
  AssignmentRunResponse,
  NormalizeResponse,
} from "@/lib/api/types";
import styles from "./actions.module.css";

type Status = "idle" | "loading" | "error";

export function BulkInvitePanel() {
  const [emails, setEmails] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [invited, setInvited] = useState<number | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setError(null);
    setInvited(null);
    try {
      const list = emails
        .split(/[\n,]/)
        .map((e) => e.trim())
        .filter(Boolean);
      const result = await api.bulkInviteJudges(list);
      setInvited(result.invited);
      setEmails("");
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Invite failed.");
    }
  }

  return (
    <section className={styles.panel}>
      <h2>Invite judges</h2>
      <p className={styles.hint}>One email per line or comma-separated.</p>
      <form onSubmit={handleSubmit} className={styles.form}>
        <textarea
          className={styles.textarea}
          value={emails}
          onChange={(e) => setEmails(e.target.value)}
          rows={4}
          placeholder="judge_d@example.org&#10;judge_e@example.org"
          required
        />
        <button
          className={styles.button}
          type="submit"
          disabled={status === "loading"}
        >
          {status === "loading" ? "Inviting..." : "Invite"}
        </button>
        {invited !== null && (
          <p className={styles.success}>Invited {invited} judge(s).</p>
        )}
        {status === "error" && error && <ErrorState>{error}</ErrorState>}
      </form>
    </section>
  );
}

export function AssignmentPanel() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssignmentRunResponse | null>(null);

  async function run() {
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await api.runAssignment();
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Assignment run failed.");
    }
  }

  return (
    <section className={styles.panel}>
      <h2>Judge assignment</h2>
      <p className={styles.hint}>
        Runs the disjoint bipartite assignment (3 reviews per project, seed 42).
      </p>
      <button className={styles.button} onClick={run} disabled={status === "loading"}>
        {status === "loading" ? "Running..." : "Run assignment"}
      </button>
      {result && (
        <p className={styles.success}>
          {result.n_assignments} assignments created
          {result.judges_with_zero_projects.length > 0 &&
            ` — ${result.judges_with_zero_projects.length} judge(s) got zero projects`}
          .
        </p>
      )}
      {status === "error" && error && <ErrorState>{error}</ErrorState>}
    </section>
  );
}

export function NormalizationPanel() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NormalizeResponse | null>(null);

  async function run() {
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await api.runNormalization();
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Normalization failed.");
    }
  }

  return (
    <section className={styles.panel}>
      <h2>Score normalization</h2>
      <p className={styles.hint}>
        Fits the additive judge-bias model across every score in the event.
      </p>
      <button className={styles.button} onClick={run} disabled={status === "loading"}>
        {status === "loading" ? "Running..." : "Run normalization"}
      </button>
      {result && (
        <p className={styles.success}>
          σ {result.raw_sigma.toFixed(3)} → {result.normalized_sigma.toFixed(3)} across{" "}
          {result.n_projects} projects, {result.n_judges} judges,{" "}
          {result.iterations} iterations
          {!result.is_connected && " (graph disconnected)"}.
        </p>
      )}
      {status === "error" && error && <ErrorState>{error}</ErrorState>}
    </section>
  );
}
