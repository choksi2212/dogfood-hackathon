"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useInView } from "react-intersection-observer";
import {
  ArrowRight,
  ArrowUpRight,
  ArrowDown,
  Rocket,
  Gavel,
  Trophy,
  SlidersHorizontal,
  Scale,
  Heart,
  ShieldCheck,
  BadgeCheck,
  PanelsTopLeft,
  Check,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { RubricPreview } from "@/components/rubric-preview";
import { GalleryBrowser } from "@/components/gallery-browser";
import { cn } from "@/lib/cn";

const steps = [
  {
    number: "01",
    icon: Rocket,
    title: "Make your move.",
    label: "Submit",
    description:
      "Ship your project, share the story, and choose your track. Give your big idea a home.",
  },
  {
    number: "02",
    icon: Gavel,
    title: "Get a fair shot.",
    label: "Judge",
    description:
      "Independent judges score against a shared rubric. Clear criteria. Thoughtful feedback.",
  },
  {
    number: "03",
    icon: Trophy,
    title: "Let good work win.",
    label: "Vote & results",
    description:
      "The community has a voice, too. Cast a vote and celebrate the projects that stand out.",
  },
];
const features = [
  {
    icon: SlidersHorizontal,
    title: "More than a gut feeling.",
    label: "Multi-criteria scoring",
    text: "Weighted rubrics, precise sliders, and considered feedback. Every score has a reason.",
    href: "/#judging",
  },
  {
    icon: Scale,
    title: "A fresh perspective.",
    label: "Pairwise comparison",
    text: "Compare two projects head-to-head. Bradley–Terry ranking turns preferences into perspective.",
    href: "/pairwise",
  },
  {
    icon: Heart,
    title: "The room gets a say.",
    label: "Community voting",
    text: "Simple or quadratic voting gives the crowd a voice alongside the judging panel.",
    href: "/vote",
  },
  {
    icon: ShieldCheck,
    title: "Nothing behind the curtain.",
    label: "Audit-grade trails",
    text: "From the first review to the final result, decisions leave a clear, traceable record.",
    href: "/#judging",
  },
  {
    icon: BadgeCheck,
    title: "Recognition that lasts.",
    label: "Signed certificates",
    text: "Public, verifiable certificates give every achievement a record you can trust.",
    href: "/certificates",
  },
  {
    icon: PanelsTopLeft,
    title: "Take the show with you.",
    label: "Embeddable gallery",
    text: "Bring the live gallery to your own site. One small embed. A whole room of big ideas.",
    href: "/widget",
  },
];

function StatsBar() {
  const reduced = useReducedMotion();
  const { ref: inViewRef, inView } = useInView({
    triggerOnce: true,
    threshold: 0.4,
  });
  const scope = useRef<HTMLDivElement>(null);
  const stats = [
    {
      value: 120,
      suffix: "+",
      label: "Submissions",
      detail: "Ideas made real",
    },
    {
      value: 36,
      suffix: "",
      label: "Judges",
      detail: "Independent perspectives",
    },
    {
      value: 8,
      suffix: "",
      label: "Tracks",
      detail: "Room for every ambition",
    },
    {
      value: 2400,
      suffix: "+",
      label: "Community votes",
      detail: "A voice for the room",
    },
  ];
  useEffect(() => {
    if (!inView || reduced !== false || !scope.current) return;
    const tweens: gsap.core.Tween[] = [];
    scope.current
      .querySelectorAll<HTMLElement>("[data-count]")
      .forEach((element) => {
        const value = Number(element.dataset.count);
        const counter = { value: 0 };
        tweens.push(
          gsap.to(counter, {
            value,
            duration: 0.8,
            ease: "power2.out",
            onUpdate: () => {
              element.textContent = Math.round(counter.value).toLocaleString(
                "en-US",
              );
            },
          }),
        );
      });
    return () => {
      tweens.forEach((tween) => tween.kill());
    };
  }, [inView, reduced]);
  return (
    <section
      aria-label="Event at a glance"
      className="relative border-y bg-bg-elevated/50"
      ref={inViewRef}
    >
      <div
        ref={scope}
        className="container-shell grid grid-cols-2 lg:grid-cols-4"
      >
        {stats.map((stat, i) => (
          <div
            key={stat.label}
            className={cn(
              "py-8 lg:py-10",
              i > 0 && "lg:border-l lg:pl-10",
              i % 2 === 1 && "pl-6",
              i < 2 && "border-b lg:border-b-0",
            )}
          >
            <p className="font-mono text-4xl tracking-tight tabular-nums lg:text-5xl">
              <span data-count={stat.value}>
                {stat.value.toLocaleString("en-US")}
              </span>
              <span className="text-accent">{stat.suffix}</span>
            </p>
            <p className="mt-3 text-sm font-medium">{stat.label}</p>
            <p className="mt-1 text-xs text-text-muted">{stat.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function LandingPage() {
  const scope = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const [scrollReady, setScrollReady] = useState(false);
  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const frame = requestAnimationFrame(() => setScrollReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);
  useGSAP(
    () => {
      if (!scrollReady || reduced !== false) return;
      gsap.to(".judging-preview", {
        y: -24,
        ease: "none",
        scrollTrigger: {
          trigger: "#judging",
          start: "top bottom",
          end: "bottom top",
          scrub: 1,
        },
      });
      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
        gsap.from(element, {
          y: 28,
          opacity: 0,
          scale: 0.985,
          duration: 0.75,
          ease: "power3.out",
          scrollTrigger: { trigger: element, start: "top 90%", once: true },
        });
      });
    },
    { scope, dependencies: [reduced, scrollReady], revertOnUpdate: true },
  );
  const enter = {
    initial: reduced ? (false as const) : { opacity: 0, y: 16 },
    animate: { opacity: 1, y: 0 },
    transition: {
      duration: 0.75,
      ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
    },
  };
  return (
    <div ref={scope} className="overflow-hidden">
      <section
        className="landing-hero relative flex min-h-[calc(100svh-4rem)] items-center"
        id="about"
      >
        <div className="container-shell relative py-24 text-center lg:py-32">
          <motion.div {...enter} className="mx-auto max-w-5xl">
            <h1 className="font-display text-[clamp(2.75rem,5.2vw,4.5rem)] leading-[1.08] font-medium tracking-display">
              Ship the next big thing.
              <br />
              <span className="text-accent">Get it judged fairly.</span>
            </h1>
            <p className="mx-auto mt-7 max-w-2xl text-base leading-relaxed text-text-secondary sm:text-lg">
              A complete judging platform: submissions, multi-criteria scoring,
              community voting, audit-grade trails. Built for organizers who
              won’t compromise.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link href="/gallery" className={buttonVariants({ size: "lg" })}>
                Browse gallery
                <ArrowRight className="size-4" />
              </Link>
              <Link
                href="/login"
                className={buttonVariants({ variant: "outline", size: "lg" })}
              >
                Sign in
                <ArrowUpRight className="size-4" />
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-text-muted">
              <span className="whitespace-nowrap">
                36 judges · 105 participants
              </span>
              <span className="font-mono text-xs whitespace-nowrap">
                SEP 25–28, 2026
              </span>
            </div>
          </motion.div>
          <a
            href="#how-it-works"
            className="mx-auto mt-16 inline-flex items-center gap-2 text-xs text-text-muted hover:text-accent"
          >
            <ArrowDown className="size-4" />
            Explore the platform
          </a>
        </div>
      </section>

      <StatsBar />
      <section id="how-it-works" className="container-shell py-24 lg:py-32">
        <div
          data-reveal
          className="mb-12 flex flex-wrap items-end justify-between gap-6"
        >
          <div>
            <p className="eyebrow mb-4">01 / From idea to recognition</p>
            <h2 className="text-3xl leading-tight font-medium tracking-display sm:text-5xl">
              You build. We handle
              <br />
              the rest.
            </h2>
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-text-secondary">
            Less time coordinating spreadsheets.
            <br />
            More time discovering what’s next.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {steps.map(({ number, icon: Icon, title, label, description }) => (
            <motion.div
              key={number}
              data-reveal
              whileHover={reduced ? undefined : { y: -2 }}
              className="interactive-card surface p-7"
            >
              <div className="mb-12 flex items-start justify-between">
                <span className="font-mono text-4xl tracking-tight text-accent/70">
                  {number}
                </span>
                <span className="flex size-12 items-center justify-center rounded-xl border border-accent/20 bg-accent-dim text-accent">
                  <Icon className="size-5" />
                </span>
              </div>
              <p className="mb-3 font-mono text-xs uppercase tracking-caps text-text-muted">
                {label}
              </p>
              <h3 className="text-2xl font-medium tracking-tight">{title}</h3>
              <p className="mt-4 text-sm leading-relaxed text-text-secondary">
                {description}
              </p>
            </motion.div>
          ))}
        </div>
      </section>
      <section id="features" className="border-y bg-bg-elevated/35">
        <div className="container-shell py-24 lg:py-32">
          <div data-reveal className="mb-12">
            <p className="eyebrow mb-4">
              02 / Serious tools. Simple experience.
            </p>
            <h2 className="text-3xl font-medium tracking-display sm:text-5xl">
              Every detail, considered.
            </h2>
            <p className="mt-5 max-w-xl text-text-secondary">
              The whole judging cycle, connected. From the first submission to
              the moment someone takes the stage.
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, label, text, href }) => (
              <div
                key={label}
                data-reveal
                className="interactive-card surface flex flex-col p-7"
              >
                <span className="mb-7 flex size-11 items-center justify-center rounded-xl bg-accent-dim text-accent">
                  <Icon className="size-5" />
                </span>
                <p className="mb-2 font-mono text-xs uppercase tracking-caps text-text-muted">
                  {label}
                </p>
                <h3 className="text-xl font-medium tracking-tight">{title}</h3>
                <p className="mt-3 flex-1 text-sm leading-relaxed text-text-secondary">
                  {text}
                </p>
                <Link
                  href={href}
                  className="text-link mt-7 w-fit text-xs font-medium text-accent"
                >
                  Learn more
                  <ArrowUpRight className="size-3.5" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="container-shell py-24 lg:py-32">
        <div
          data-reveal
          className="mb-10 flex flex-wrap items-end justify-between gap-6"
        >
          <div>
            <p className="eyebrow mb-4">03 / Built here. Going places.</p>
            <h2 className="text-3xl font-medium tracking-display sm:text-5xl">
              What shipped.
            </h2>
            <p className="mt-4 text-text-secondary">
              Real projects. Real ambition. Meet the class of 2026.
            </p>
          </div>
          <Link
            href="/gallery"
            className="text-link text-sm font-medium text-accent"
          >
            Browse all submissions
            <ArrowRight className="size-4" />
          </Link>
        </div>
        <GalleryBrowser preview />
      </section>
      <section id="judging" className="border-t bg-bg-elevated/35">
        <div className="container-shell grid items-center gap-16 py-24 lg:grid-cols-2 lg:py-32">
          <div data-reveal>
            <p className="eyebrow mb-4">04 / Confidence in every score</p>
            <h2 className="text-3xl leading-tight font-medium tracking-display sm:text-5xl">
              Fairness isn’t a feature.
              <br />
              <span className="text-text-secondary">It’s the foundation.</span>
            </h2>
            <p className="mt-6 max-w-lg leading-relaxed text-text-secondary">
              A great hackathon deserves a judging process as thoughtful as the
              projects in it.
            </p>
            <ol className="mt-8 space-y-6">
              {[
                {
                  title: "One rubric, a shared standard",
                  text: "Every judge works from the same weighted criteria. No moving goalposts.",
                },
                {
                  title: "Independent reviews, better perspective",
                  text: "Assigned batches and head-to-head comparisons bring different viewpoints together.",
                },
                {
                  title: "A trail you can stand behind",
                  text: "Scores, votes, and decisions stay traceable. Recognition comes with a verifiable record.",
                },
              ].map((step, i) => (
                <li key={step.title} className="flex gap-4">
                  <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full border border-accent/30 font-mono text-xs text-accent">
                    {i + 1}
                  </span>
                  <div>
                    <h3 className="text-sm font-medium">{step.title}</h3>
                    <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-text-secondary">
                      {step.text}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
          <div data-reveal className="judging-preview px-3 pb-5 lg:px-10">
            <RubricPreview large />
          </div>
        </div>
      </section>
      <section className="relative overflow-hidden border-y border-cyan-300/20 bg-[#0b2a34] text-white">
        <div
          aria-hidden="true"
          className="mesh-grid moving-grid absolute inset-0 opacity-[.05]"
        />
        <div className="container-shell relative flex flex-wrap items-center justify-between gap-8 py-20 lg:py-24">
          <div data-reveal>
            <p className="mb-4 flex items-center gap-2 font-mono text-xs uppercase tracking-caps text-cyan-200">
              <Check className="size-4" />
              Your next chapter starts here
            </p>
            <h2 className="text-4xl font-medium tracking-display sm:text-6xl">
              Ready to ship?
            </h2>
            <p className="mt-4 text-sm text-cyan-100/75">
              Bring the idea. We’ll make room for it.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/submit"
              className={cn(
                buttonVariants({ size: "lg" }),
                "bg-cyan-200 text-slate-950 hover:bg-cyan-100 hover:shadow-sm",
              )}
            >
              Submit your project
              <ArrowUpRight className="size-4" />
            </Link>
            <Link
              href="/gallery"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white",
              )}
            >
              Explore the gallery
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
