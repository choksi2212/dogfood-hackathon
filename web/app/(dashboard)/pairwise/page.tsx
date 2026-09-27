"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { RouteLoading } from "@/components/route-loading";
import { cn } from "@/lib/utils";
import type { PairwiseWinner, Submission } from "@/lib/api/types";

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
    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" />
        <AlertDescription>Could not load projects: {loadError}</AlertDescription>
      </Alert>
    );
  }

  if (pool === null) {
    return <RouteLoading />;
  }

  if (pool.length < 2) {
    return <p className="text-muted-foreground">Need at least two submitted projects to compare.</p>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Pairwise compare</h1>
          <p className="mt-1 text-muted-foreground">
            ← left wins · → right wins · space / T tie · {count} compared this session
          </p>
        </div>
        <Link
          href="/pairwise/ranking"
          className={cn(buttonVariants({ variant: "outline" }))}
        >
          View ranking
        </Link>
      </div>
      {voteError && (
        <Alert variant="destructive" className="mt-4">
          <AlertCircle className="size-4" />
          <AlertDescription>{voteError}</AlertDescription>
        </Alert>
      )}
      {pair && (
        <div className="mt-6 grid grid-cols-[1fr_auto_1fr] items-stretch gap-3">
          <button
            className="flex flex-col rounded-lg border bg-card p-4 text-left shadow-xs transition hover:border-primary hover:shadow-md"
            onClick={() => choose("left")}
          >
            <span className="text-lg font-semibold">{pair[0].name}</span>
            <span className="mt-2 text-muted-foreground">{pair[0].tagline}</span>
          </button>
          <button
            className="self-center rounded-md border px-3 py-2 text-sm font-medium text-muted-foreground transition hover:border-primary hover:text-primary"
            onClick={() => choose("tie")}
          >
            Tie
          </button>
          <button
            className="flex flex-col rounded-lg border bg-card p-4 text-left shadow-xs transition hover:border-primary hover:shadow-md"
            onClick={() => choose("right")}
          >
            <span className="text-lg font-semibold">{pair[1].name}</span>
            <span className="mt-2 text-muted-foreground">{pair[1].tagline}</span>
          </button>
        </div>
      )}
    </div>
  );
}
