"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState } from "@/components/StateMessage";
import type { EventDetail } from "@/lib/api/types";
import styles from "./score.module.css";

type Criterion = NonNullable<EventDetail["rubric"]>["criteria"][number];

type Status = "idle" | "saving" | "submitting" | "error";

export function ScoreForm({
  projectId,
  criteria,
}: {
  projectId: string;
  criteria: Criterion[];
}) {
  const router = useRouter();
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(criteria.map((c) => [c.id, c.min])),
  );
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submittedAt, setSubmittedAt] = useState<string | null>(null);

  function setValue(criterionId: string, value: number) {
    setValues((v) => ({ ...v, [criterionId]: value }));
    setSaved(false);
  }

  async function handleSave() {
    setStatus("saving");
    setError(null);
    try {
      await api.saveScore(projectId, {
        scores: Object.entries(values).map(([criterion_id, value]) => ({
          criterion_id,
          value,
        })),
        comment,
      });
      setSaved(true);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Save failed.");
    }
  }

  async function handleSubmit() {
    setStatus("submitting");
    setError(null);
    try {
      await handleSave();
      const result = await api.submitScore(projectId);
      setSubmittedAt(result.submitted_at);
      setStatus("idle");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Submit failed.");
    }
  }

  if (submittedAt) {
    return (
      <p className={styles.done}>
        Submitted at {new Date(submittedAt).toLocaleString()}.
      </p>
    );
  }

  return (
    <div className={styles.form}>
      {criteria.map((criterion) => (
        <div key={criterion.id} className={styles.criterion}>
          <div className={styles.criterionHeader}>
            <span className={styles.criterionName}>{criterion.name}</span>
            <span className={styles.criterionWeight}>
              weight {criterion.weight}
            </span>
          </div>
          {criterion.description && (
            <p className={styles.criterionDescription}>
              {criterion.description}
            </p>
          )}
          <div className={styles.slider}>
            <input
              type="range"
              min={criterion.min}
              max={criterion.max}
              value={values[criterion.id] ?? criterion.min}
              onChange={(e) =>
                setValue(criterion.id, Number(e.target.value))
              }
            />
            <span className={styles.sliderValue}>
              {values[criterion.id] ?? criterion.min} / {criterion.max}
            </span>
          </div>
        </div>
      ))}

      <label className={styles.commentField}>
        Comment (optional)
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
        />
      </label>

      <div className={styles.actions}>
        <button
          className={styles.saveButton}
          onClick={handleSave}
          disabled={status === "saving" || status === "submitting"}
        >
          {status === "saving" ? "Saving..." : "Save draft"}
        </button>
        <button
          className={styles.submitButton}
          onClick={handleSubmit}
          disabled={status === "saving" || status === "submitting"}
        >
          {status === "submitting" ? "Submitting..." : "Submit review"}
        </button>
        {saved && status === "idle" && (
          <span className={styles.savedHint}>Saved.</span>
        )}
      </div>
      {status === "error" && error && <ErrorState>{error}</ErrorState>}
    </div>
  );
}
