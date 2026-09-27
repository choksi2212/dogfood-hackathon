"use client";

import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RouteLoading } from "@/components/route-loading";
import type { Submission } from "@/lib/api/types";

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
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" />
        <AlertDescription>Could not load the gallery: {loadError}</AlertDescription>
      </Alert>
    );
  }

  if (items === null) {
    return <RouteLoading />;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Vote</h1>
      <p className="mt-1 text-muted-foreground">
        One vote per project — cast it, or take it back.
      </p>
      {items.length === 0 ? (
        <Alert className="mt-6">
          <AlertDescription>No projects to vote on yet.</AlertDescription>
        </Alert>
      ) : (
        <ul className="mt-6 flex flex-col gap-2">
          {items.map((item) => {
            const state = voteState[item.id] ?? "idle";
            return (
              <li key={item.id}>
                <Card className="flex flex-row items-center justify-between gap-3 p-4">
                  <div>
                    <span className="font-semibold">{item.name}</span>
                    <p className="mt-1 text-sm text-muted-foreground">{item.tagline}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {state === "voted" ? (
                      <Button variant="outline" onClick={() => retractVote(item.id)}>
                        Retract
                      </Button>
                    ) : (
                      <Button disabled={state === "pending"} onClick={() => castVote(item.id)}>
                        {state === "pending" ? "Voting…" : "Vote"}
                      </Button>
                    )}
                    {rowError[item.id] && (
                      <p className="text-xs text-destructive">{rowError[item.id]}</p>
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
