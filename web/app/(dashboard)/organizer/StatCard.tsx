"use client";

import { useEffect, useState } from "react";
import { animate, motion, useReducedMotion } from "motion/react";
import { Rocket, ShieldCheck, Users, UserRoundCheck } from "lucide-react";

const icons = {
  judges: UserRoundCheck,
  organizers: ShieldCheck,
  participants: Users,
  submissions: Rocket,
};

export function StatCard({
  label,
  value,
  detail,
  index,
}: {
  label: string;
  value: number | null;
  detail: string;
  index: number;
}) {
  const reducedMotion = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const Icon = icons[label.toLowerCase() as keyof typeof icons] ?? Rocket;

  useEffect(() => {
    if (reducedMotion || value === null) return;
    const animation = animate(0, value, {
      duration: 0.6,
      ease: "easeOut",
      onUpdate: (next) => setDisplay(Math.round(next)),
    });
    return () => animation.stop();
  }, [value, reducedMotion]);

  return (
    <motion.div
      initial={reducedMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      className="surface interactive-card rounded-xl p-5"
    >
      <div className="mb-5 flex items-center justify-between">
        <span className="text-sm text-text-secondary">{label}</span>
        <span className="flex size-9 items-center justify-center rounded-lg border border-accent/15 bg-accent-dim text-accent">
          <Icon className="size-[18px]" />
        </span>
      </div>
      <p
        className="font-mono text-4xl tracking-tight tabular-nums"
        aria-label={
          value === null
            ? `${label} count unavailable`
            : `${value} ${label.toLowerCase()}`
        }
      >
        <span aria-hidden="true">
          {value === null
            ? "—"
            : (reducedMotion ? value : (display ?? value)).toLocaleString()}
        </span>
      </p>
      <p className="mt-3 text-xs text-text-muted">{detail}</p>
    </motion.div>
  );
}
