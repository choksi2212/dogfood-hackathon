"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/Card";
import { Button } from "@/components/Button";
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
      <PageHeader title="Vote" description="One vote per project — cast it, or take it back." />
      {items.length === 0 ? (
        <EmptyState>No projects to vote on yet.</EmptyState>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => {
            const state = voteState[item.id] ?? "idle";
            return (
              <li key={item.id}>
                <Card className={styles.row}>
                  <div>
                    <span className={styles.name}>{item.name}</span>
                    <p className={styles.tagline}>{item.tagline}</p>
                  </div>
                  <div className={styles.rowEnd}>
                    {state === "voted" ? (
                      <Button variant="secondary" onClick={() => retractVote(item.id)}>
                        Retract
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        loading={state === "pending"}
                        onClick={() => castVote(item.id)}
                      >
                        Vote
                      </Button>
                    )}
                    {rowError[item.id] && (
                      <p className={styles.rowError}>{rowError[item.id]}</p>
                    )}
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
