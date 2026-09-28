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
  UserRound,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { AuthShell } from "../login/auth-shell";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const strength = [
    password.length >= 8,
    password.length >= 12,
    /[a-z]/.test(password) && /[A-Z]/.test(password),
    /\d/.test(password) && /[^a-zA-Z0-9]/.test(password),
  ].filter(Boolean).length;
  const strengthLabel =
    password.length === 0
      ? "At least 8 characters"
      : ["Keep going", "Getting started", "Good", "Strong", "Excellent"][
          strength
        ];

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.register({ name: name.trim(), email: email.trim(), password });
      router.push("/gallery");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError && err.status < 500
          ? err.code === "unknown_error"
            ? "We couldn’t create your account. Check your details, or sign in if you already have one."
            : err.message
          : "We couldn’t create your account. Please try again in a moment.",
      );
      setLoading(false);
    }
  }

  return (
    <AuthShell mode="register">
      <Card className="w-full rounded-2xl border-border bg-bg-elevated shadow-elevated">
        <CardHeader className="px-7 pt-8 pb-6 sm:px-9 sm:pt-9">
          <p className="eyebrow mb-2">THE NEXT BIG THING STARTS HERE</p>
          <h1 className="font-display text-3xl font-medium tracking-display">
            Make yourself at home.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            Create your account and explore what’s shipping.
          </p>
        </CardHeader>
        <CardContent className="px-7 pb-8 sm:px-9 sm:pb-9">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name">Your name</Label>
              <div className="relative">
                <UserRound
                  aria-hidden="true"
                  className="pointer-events-none absolute top-3.5 left-3.5 size-4 text-text-muted"
                />
                <Input
                  id="name"
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="How should we call you?"
                  required
                  disabled={loading}
                  className="h-12 rounded-xl border-border bg-bg-overlay pl-10"
                />
              </div>
            </div>
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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@yourteam.com"
                  required
                  disabled={loading}
                  className="h-12 rounded-xl border-border bg-bg-overlay pl-10"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Create a password</Label>
              <div className="relative">
                <LockKeyhole
                  aria-hidden="true"
                  className="pointer-events-none absolute top-3.5 left-3.5 size-4 text-text-muted"
                />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  minLength={8}
                  aria-describedby="password-strength"
                  required
                  disabled={loading}
                  className="h-12 rounded-xl border-border bg-bg-overlay pr-12 pl-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="absolute top-2.5 right-2.5 text-text-secondary"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </Button>
              </div>
              <div id="password-strength" className="flex items-center gap-3">
                <div className="flex gap-1.5" aria-hidden="true">
                  {Array.from({ length: 4 }, (_, index) => (
                    <span
                      key={index}
                      className={cn(
                        "size-2 rounded-full transition-colors",
                        index < strength
                          ? strength >= 3
                            ? "bg-success"
                            : "bg-accent"
                          : "bg-border-strong",
                      )}
                    />
                  ))}
                </div>
                <span className="text-xs text-text-muted">{strengthLabel}</span>
              </div>
            </div>
            {error && (
              <Alert variant="destructive" role="alert">
                <AlertCircle className="size-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button
              size="lg"
              type="submit"
              disabled={loading}
              className="w-full"
            >
              {loading ? (
                <>
                  <LoaderCircle className="size-4 motion-safe:animate-spin" />
                  Creating your account…
                </>
              ) : (
                <>
                  Create account
                  <ArrowRight className="size-4" />
                </>
              )}
            </Button>
          </form>
          <p className="mt-5 text-xs leading-relaxed text-text-muted">
            You’ll be signed in automatically. Your organizer grants
            participant, judge, or organizer access to the event.
          </p>
          <p className="mt-6 border-t border-border pt-6 text-center text-sm text-text-secondary">
            Already part of the crew?{" "}
            <Link
              href="/login"
              className="font-medium text-accent hover:text-accent-hover"
            >
              Sign in <span aria-hidden="true">→</span>
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
