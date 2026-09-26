"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import styles from "./submit.module.css";

type Status = "idle" | "loading" | "success" | "error";

export default function SubmitPage() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [tagline, setTagline] = useState("");
  const [description, setDescription] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage(null);
    try {
      await api.submit({ name, tagline, description });
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof ApiError ? err.message : "Something went wrong.",
      );
    }
  }

  if (status === "success") {
    return <p>Submission received. You can edit it until the deadline.</p>;
  }

  return (
    <div>
      <h1>Submit your project</h1>
      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.field}>
          Project name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label className={styles.field}>
          Tagline
          <input
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            maxLength={140}
          />
        </label>
        <label className={styles.field}>
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
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
