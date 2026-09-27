"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { ErrorState, LoadingState } from "@/components/StateMessage";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/Button";
import type { PairwiseWinner, Submission } from "@/lib/api/types";
import styles from "./pairwise.module.css";

function pickPair(
  pool: Submission[],
  seenKeys: Set<string>,
): [Submission, Submission] | null {
  if (pool.length < 2) return null;

  // Try a bounded number of random draws to avoid a pair already
  // compared this session; fall back to any distinct pair once the
  // pool is exhausted rather than getting stuck.
  for (let attempt = 0; attempt < 20; attempt++) {
    const a = pool[Math.floor(Math.random() * pool.length)];
    let b = pool[Math.floor(Math.random() * pool.length)];
    while (b.id === a.id) {
      b = pool[Math.floor(Math.random() * pool.length)];
    }
    const key = [a.id, b.id].sort().join(":");
    if (!seenKeys.has(key)) {
      return [a, b];
    }
  }
  const a = pool[Math.floor(Math.random() * pool.length)];
  let b = pool[Math.floor(Math.random() * pool.length)];
  while (b.id === a.id) {
    b = pool[Math.floor(Math.random() * pool.length)];
  }
  return [a, b];
}

export default function PairwisePage() {
  const [pool, setPool] = useState<Submission[] | null>(null);
  const [pair, setPair] = useState<[Submission, Submission] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [voteError, setVoteError] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const seenKeys = useRef(new Set<string>());

  useEffect(() => {
    api
      .gallery()
      .then((data) => {
        setPool(data.items);
        setPair(pickPair(data.items, seenKeys.current));
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "Something went wrong."),
      );
  }, []);

  const choose = useCallback(
    async (winner: PairwiseWinner) => {
      if (!pair) return;
      const [left, right] = pair;
      setVoteError(null);
      try {
        await api.pairwiseBallot({
          left_id: left.id,
          right_id: right.id,
          winner,
        });
        seenKeys.current.add([left.id, right.id].sort().join(":"));
        setCount((c) => c + 1);
        setPair(pool ? pickPair(pool, seenKeys.current) : null);
      } catch (err) {
        setVoteError(err instanceof ApiError ? err.message : "Vote failed.");
      }
    },
    [pair, pool],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") choose("left");
      else if (e.key === "ArrowRight") choose("right");
      else if (e.key === " " || e.key.toLowerCase() === "t") {
        e.preventDefault();
        choose("tie");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [choose]);

  if (loadError) {
    return <ErrorState>Could not load projects: {loadError}</ErrorState>;
  }

  if (pool === null) {
    return <LoadingState>Loading projects...</LoadingState>;
  }

  if (pool.length < 2) {
    return <p>Need at least two submitted projects to compare.</p>;
  }

  return (
    <div>
      <PageHeader
        title="Pairwise compare"
        description={`← left wins · → right wins · space / T tie · ${count} compared this session`}
        actions={
          <Link href="/pairwise/ranking">
            <Button variant="secondary">View ranking</Button>
          </Link>
        }
      />
      {voteError && <ErrorState>{voteError}</ErrorState>}
      {pair && (
        <div className={styles.arena}>
          <button className={styles.card} onClick={() => choose("left")}>
            <span className={styles.cardTitle}>{pair[0].name}</span>
            <span className={styles.cardTagline}>{pair[0].tagline}</span>
          </button>
          <button className={styles.tieButton} onClick={() => choose("tie")}>
            Tie
          </button>
          <button className={styles.card} onClick={() => choose("right")}>
            <span className={styles.cardTitle}>{pair[1].name}</span>
            <span className={styles.cardTagline}>{pair[1].tagline}</span>
          </button>
        </div>
      )}
    </div>
  );
}
