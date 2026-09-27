"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCircle } from "lucide-react";

type Role = "organizer" | "judge" | "participant";

const ROLE_COPY: Record<Role, { label: string; hint: string; landing: string }> = {
  organizer: {
    label: "Organizer",
    hint: "Manage judges, run assignment and normalization, publish results.",
    landing: "/organizer",
  },
  judge: {
    label: "Judge",
    hint: "Score your assigned batch and compare projects head-to-head.",
    landing: "/judge",
  },
  participant: {
    label: "Participant",
    hint: "Submit your project and vote on others.",
    landing: "/submit",
  },
};

export default function LoginPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("participant");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
        setErrorMessage("This account has no role on this event.");
        return;
      }

      // Honor the tab the visitor picked if the account actually holds
      // that role; otherwise land them on the role they do hold instead
      // of a dead end.
      const effectiveRole = (membership.role in ROLE_COPY ? membership.role : role) as Role;
      router.push(ROLE_COPY[effectiveRole]?.landing ?? "/gallery");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col justify-center px-4 py-24">
      <Card>
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Choose the role you&apos;re signing in as.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={role} onValueChange={(v) => setRole(v as Role)}>
            <TabsList className="w-full">
              {(Object.keys(ROLE_COPY) as Role[]).map((r) => (
                <TabsTrigger key={r} value={r} className="flex-1">
                  {ROLE_COPY[r].label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <p className="mt-3 text-sm text-muted-foreground">{ROLE_COPY[role].hint}</p>

          <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={status === "loading"}>
              {status === "loading" ? "Logging in…" : `Log in as ${ROLE_COPY[role].label}`}
            </Button>
            {status === "error" && errorMessage && (
              <Alert variant="destructive">
                <AlertCircle className="size-4" />
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
