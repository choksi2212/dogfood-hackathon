"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/StateMessage";
import type { Submission } from "@/lib/api/types";
import styles from "./vote.module.css";

// The backend has no "did I already vote" read endpoint (Vote rows are
// keyed by an opaque voter_key the frontend never sees), so ballot
// state here is optimistic and local to this page load — a refresh
// forgets it. Casting and retracting are both idempotent server-side,
// so this is safe, just not persisted across visits.
type VoteState = "idle" | "voted" | "pending";

export default function VotePage() {
  const [items, setItems] = useState<Submission[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [voteState, setVoteState] = useState<Record<string, VoteState>>({});
  const [rowError, setRowError] = useState<Record<string, string>>({});

  useEffect(() => {
    api
      .gallery()
      .then((data) => setItems(data.items))
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Something went wrong."),
      );
  }, []);

  async function castVote(id: string) {
    setVoteState((s) => ({ ...s, [id]: "pending" }));
    setRowError((e) => ({ ...e, [id]: "" }));
    try {
      await api.vote(id);
      setVoteState((s) => ({ ...s, [id]: "voted" }));
    } catch (err) {
      setVoteState((s) => ({ ...s, [id]: "idle" }));
      setRowError((e) => ({
        ...e,
        [id]: err instanceof ApiError ? err.message : "Vote failed.",
      }));
    }
  }

  async function retractVote(id: string) {
    setVoteState((s) => ({ ...s, [id]: "pending" }));
    setRowError((e) => ({ ...e, [id]: "" }));
    try {
      await api.retractVote(id);
      setVoteState((s) => ({ ...s, [id]: "idle" }));
    } catch (err) {
      setVoteState((s) => ({ ...s, [id]: "voted" }));
      setRowError((e) => ({
        ...e,
        [id]: err instanceof ApiError ? err.message : "Retract failed.",
      }));
    }
  }

  if (loadError) {
    return <ErrorState>Could not load the gallery: {loadError}</ErrorState>;
  }

  if (items === null) {
    return <LoadingState>Loading gallery...</LoadingState>;
  }

  return (
    <div>
      <h1>Vote</h1>
      {items.length === 0 ? (
        <EmptyState>No projects to vote on yet.</EmptyState>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => {
            const state = voteState[item.id] ?? "idle";
            return (
              <li key={item.id} className={styles.row}>
                <div>
                  <span className={styles.name}>{item.name}</span>
                  <p className={styles.tagline}>{item.tagline}</p>
                </div>
                {state === "voted" ? (
                  <button
                    className={styles.retractButton}
                    onClick={() => retractVote(item.id)}
                  >
                    Retract
                  </button>
                ) : (
                  <button
                    className={styles.voteButton}
                    disabled={state === "pending"}
                    onClick={() => castVote(item.id)}
                  >
                    {state === "pending" ? "..." : "Vote"}
                  </button>
                )}
                {rowError[item.id] && (
                  <p className={styles.rowError}>{rowError[item.id]}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
