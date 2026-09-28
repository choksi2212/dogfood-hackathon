"use client";
import { Check, SlidersHorizontal, ShieldCheck } from "lucide-react";

export function RubricPreview({ large = false }: { large?: boolean }) {
  const criteria = [
    { name: "Innovation", value: 8.5, weight: "30%" },
    { name: "Technical execution", value: 9, weight: "40%" },
    { name: "Real-world impact", value: 8, weight: "30%" },
  ];
  return (
    <div
      className="mx-auto w-full max-w-md rounded-2xl border bg-bg-elevated shadow-card"
      aria-label="Illustrative scoring interface"
    >
      <div className="flex items-center justify-between gap-3 border-b px-6 py-5">
        <span className="flex items-center gap-2 text-sm font-medium">
          <SlidersHorizontal
            aria-hidden="true"
            className="size-4 text-accent"
          />
          Judge workspace
        </span>
        <span className="rounded-full bg-success-dim px-2.5 py-1 text-xs text-success">
          Draft saved
        </span>
      </div>
      <div className="p-6">
        <p className="mb-7 text-lg font-medium tracking-tight">
          A shared standard for great work.
        </p>
        <div className="space-y-7">
          {criteria.map((c) => (
            <div key={c.name}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <span className="text-sm text-text-secondary">{c.name}</span>
                <span className="font-mono text-lg tabular-nums">
                  {c.value.toFixed(1)}
                  <span className="ml-1 text-xs text-text-muted">/10</span>
                </span>
              </div>
              <div className="relative h-1.5 rounded-full bg-bg-overlay">
                <div
                  className="absolute inset-0 origin-left rounded-full bg-accent"
                  style={{ transform: `scaleX(${c.value / 10})` }}
                />
                <span
                  className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-bg-elevated"
                  style={{ left: `${c.value * 10}%` }}
                />
              </div>
              {large && (
                <p className="mt-3 font-mono text-xs text-text-muted">
                  Weight {c.weight}
                </p>
              )}
            </div>
          ))}
        </div>
        <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t pt-5">
          <span className="flex items-center gap-1.5 text-xs text-text-secondary">
            <ShieldCheck aria-hidden="true" className="size-4" />
            Every score, accounted for.
          </span>
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <Check aria-hidden="true" className="size-4" />
            Review ready
          </span>
        </div>
      </div>
    </div>
  );
}
