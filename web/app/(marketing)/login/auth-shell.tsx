"use client";

import { motion, useReducedMotion } from "motion/react";
import { Check, Trophy } from "lucide-react";
import { Brand } from "@/components/brand";

export function AuthShell({
  children,
  mode,
}: {
  children: React.ReactNode;
  mode: "login" | "register";
}) {
  const reducedMotion = useReducedMotion();
  return (
    <div className="container-shell grid min-h-[calc(100svh-4rem)] items-center gap-10 py-12 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:py-16">
      <motion.section
        initial={reducedMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="rounded-2xl border border-border bg-bg-elevated px-7 py-9 text-text-primary sm:px-10 lg:flex lg:min-h-[560px] lg:flex-col lg:justify-between lg:px-12 lg:py-12"
      >
        <div>
          <Brand className="text-xl text-text-primary" />
          <p className="mt-10 font-mono text-xs tracking-caps text-accent">
            HACK HAMSTER 2026 · BUILT FOR BUILDERS
          </p>
          <h2 className="mt-4 max-w-sm font-display text-3xl leading-tight font-medium tracking-display sm:text-4xl">
            {mode === "login" ? (
              <>
                Welcome back.
                <br />
                <span className="text-accent">Let’s make it count.</span>
              </>
            ) : (
              <>
                Big ideas.
                <br />
                <span className="text-accent">Better together.</span>
              </>
            )}
          </h2>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-text-secondary">
            {mode === "login"
              ? "From the first submission to the final score, your next chapter is right here."
              : "Join the people turning late-night inspiration into something worth showing the world."}
          </p>
        </div>
        <div aria-hidden="true" className="my-9 text-accent-2">
          <Trophy className="size-20" strokeWidth={1} />
        </div>
        <div className="flex items-start gap-3 border-t border-border pt-6">
          <Check
            className="mt-0.5 size-4 shrink-0 text-accent"
            aria-hidden="true"
          />
          <p className="text-sm leading-relaxed text-text-secondary">
            Thoughtful judging. Transparent results.
            <br />
            <span className="text-text-primary">
              A platform worthy of what you ship.
            </span>
          </p>
        </div>
      </motion.section>
      <motion.div
        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: reducedMotion ? 0 : 0.08 }}
        className="mx-auto w-full max-w-md"
      >
        {children}
      </motion.div>
    </div>
  );
}
