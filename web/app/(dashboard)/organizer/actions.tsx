"use client";

import { useState } from "react";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  AssignmentRunResponse,
  NormalizeResponse,
} from "@/lib/api/types";

type Status = "idle" | "loading" | "error";

export function BulkInvitePanel() {
  const [emails, setEmails] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [invited, setInvited] = useState<number | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setError(null);
    setInvited(null);
    try {
      const list = emails
        .split(/[\n,]/)
        .map((e) => e.trim())
        .filter(Boolean);
      const result = await api.bulkInviteJudges(list);
      setInvited(result.invited);
      setEmails("");
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Invite failed.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invite judges</CardTitle>
        <CardDescription>One email per line or comma-separated.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col items-start gap-3">
          <div className="flex w-full flex-col gap-2">
            <Label htmlFor="invite-emails">Emails</Label>
            <Textarea
              id="invite-emails"
              value={emails}
              onChange={(e) => setEmails(e.target.value)}
              rows={4}
              placeholder={"judge_d@example.org\njudge_e@example.org"}
              required
            />
          </div>
          <Button type="submit" disabled={status === "loading"}>
            {status === "loading" ? "Inviting…" : "Invite"}
          </Button>
          {invited !== null && (
            <p className="text-sm font-medium text-success">Invited {invited} judge(s).</p>
          )}
          {status === "error" && error && (
            <Alert variant="destructive">
              <AlertCircle className="size-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

export function AssignmentPanel() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssignmentRunResponse | null>(null);

  async function run() {
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await api.runAssignment();
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Assignment run failed.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Judge assignment</CardTitle>
        <CardDescription>
          Runs the disjoint bipartite assignment (3 reviews per project, seed 42).
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-3">
        <Button variant="outline" onClick={run} disabled={status === "loading"}>
          {status === "loading" ? "Running…" : "Run assignment"}
        </Button>
        {result && (
          <p className="text-sm font-medium text-success">
            {result.n_assignments} assignments created
            {result.judges_with_zero_projects.length > 0 &&
              ` — ${result.judges_with_zero_projects.length} judge(s) got zero projects`}
            .
          </p>
        )}
        {status === "error" && error && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

export function NormalizationPanel() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NormalizeResponse | null>(null);

  async function run() {
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await api.runNormalization();
      setResult(data);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Normalization failed.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Score normalization</CardTitle>
        <CardDescription>
          Fits the additive judge-bias model across every score in the event.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-3">
        <Button variant="outline" onClick={run} disabled={status === "loading"}>
          {status === "loading" ? "Running…" : "Run normalization"}
        </Button>
        {result && (
          <p className="text-sm font-medium text-success">
            σ {result.raw_sigma.toFixed(3)} → {result.normalized_sigma.toFixed(3)} across{" "}
            {result.n_projects} projects, {result.n_judges} judges,{" "}
            {result.iterations} iterations
            {!result.is_connected && " (graph disconnected)"}.
          </p>
        )}
        {status === "error" && error && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
