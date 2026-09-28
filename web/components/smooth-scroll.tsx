"use client";
import { useEffect } from "react";
import { useReducedMotion } from "motion/react";
import Lenis from "lenis";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function SmoothScroll({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced !== false) return;
    const lenis = new Lenis({
      duration: 1.05,
      smoothWheel: true,
      anchors: true,
    });
    let frame = 0;
    const tick = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    lenis.on("scroll", ScrollTrigger.update);
    return () => {
      cancelAnimationFrame(frame);
      lenis.destroy();
    };
  }, [reduced]);
  return children;
}
