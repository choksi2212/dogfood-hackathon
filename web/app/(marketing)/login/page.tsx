"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  Mail,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuthShell } from "./auth-shell";

type Role = "organizer" | "judge" | "participant";
const ROLE_COPY: Record<
  Role,
  { label: string; hint: string; landing: string }
> = {
  organizer: {
    label: "Organizer",
    hint: "Bring the people, projects, and judging together.",
    landing: "/organizer",
  },
  judge: {
    label: "Judge",
    hint: "Give great ideas the thoughtful review they deserve.",
    landing: "/judge",
  },
  participant: {
    label: "Participant",
    hint: "Your next big thing starts with a submission.",
    landing: "/submit",
  },
};

export default function LoginPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("participant");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage(null);
    try {
      const user = await api.login({ email, password });
      const membership = user.memberships.find((m) => m.event === EVENT_SLUG);
      if (!membership) {
        setStatus("error");
        setErrorMessage(
          "This account has no role on this event. Ask your organizer to add you to the hackathon.",
        );
        return;
      }
      const effectiveRole = (
        membership.role in ROLE_COPY ? membership.role : role
      ) as Role;
      router.push(ROLE_COPY[effectiveRole]?.landing ?? "/gallery");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof ApiError && err.status < 500
          ? err.message
          : "We couldn’t sign you in. Please try again in a moment.",
      );
    }
  }

  return (
    <AuthShell mode="login">
      <Card className="w-full rounded-2xl border-border bg-bg-elevated shadow-elevated">
        <CardHeader className="px-7 pt-8 pb-6 sm:px-9 sm:pt-9">
          <p className="eyebrow mb-2">YOUR WORKSPACE AWAITS</p>
          <h1 className="font-display text-3xl font-medium tracking-display">
            Good to see you.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            Sign in and pick up where you left off.
          </p>
        </CardHeader>
        <CardContent className="px-7 pb-8 sm:px-9 sm:pb-9">
          <Tabs value={role} onValueChange={(value) => setRole(value as Role)}>
            <TabsList className="h-11 w-full rounded-xl bg-bg-overlay p-1">
              {(Object.keys(ROLE_COPY) as Role[]).map((item) => (
                <TabsTrigger
                  key={item}
                  value={item}
                  className="flex-1 rounded-lg text-xs sm:text-sm"
                >
                  {ROLE_COPY[item].label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <p className="mt-4 min-h-10 text-sm leading-relaxed text-text-secondary">
            {ROLE_COPY[role].hint}
          </p>
          <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <div className="relative">
                <Mail
                  aria-hidden="true"
                  className="pointer-events-none absolute top-3.5 left-3.5 size-4 text-text-muted"
                />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@yourteam.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-12 rounded-xl border-border bg-bg-overlay pl-10"
                  disabled={status === "loading"}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <LockKeyhole
                  aria-hidden="true"
                  className="pointer-events-none absolute top-3.5 left-3.5 size-4 text-text-muted"
                />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-12 rounded-xl border-border bg-bg-overlay pr-12 pl-10"
                  disabled={status === "loading"}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute top-2.5 right-2.5 text-text-secondary"
                >
                  {showPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </Button>
              </div>
            </div>
            {status === "error" && errorMessage && (
              <Alert variant="destructive" role="alert">
                <AlertCircle className="size-4" />
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={status === "loading"}
            >
              {status === "loading" ? (
                <>
                  <LoaderCircle className="size-4 motion-safe:animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in as {ROLE_COPY[role].label}
                  <ArrowRight className="size-4" />
                </>
              )}
            </Button>
          </form>
          <p className="mt-7 text-center text-sm text-text-secondary">
            Don’t have an account?{" "}
            <Link
              href="/register"
              className="font-medium text-accent hover:text-accent-hover"
            >
              Register <span aria-hidden="true">→</span>
            </Link>
          </p>
        </CardContent>
      </Card>
      <p className="mt-5 text-center text-xs leading-relaxed text-text-muted">
        One account. A fair shot for every great idea.
      </p>
    </AuthShell>
  );
}
