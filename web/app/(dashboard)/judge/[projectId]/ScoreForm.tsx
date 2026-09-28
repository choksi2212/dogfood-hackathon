"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { EventDetail } from "@/lib/api/types";

type Criterion = NonNullable<EventDetail["rubric"]>["criteria"][number];

type Status = "idle" | "saving" | "submitting" | "error";

export function ScoreForm({
  projectId,
  criteria,
  initialValues = {},
  initialSubmittedAt = null,
}: {
  projectId: string;
  criteria: Criterion[];
  initialValues?: Record<string, number>;
  initialSubmittedAt?: string | null;
}) {
  const router = useRouter();
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(criteria.map((c) => [c.id, initialValues[c.id] ?? c.min])),
  );
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submittedAt, setSubmittedAt] = useState<string | null>(initialSubmittedAt);

  function setValue(criterionId: string, value: number) {
    setValues((v) => ({ ...v, [criterionId]: value }));
    setSaved(false);
  }

  async function handleSave() {
    setStatus("saving");
    setError(null);
    try {
      await api.saveScore(projectId, {
        scores: Object.entries(values).map(([criterion_id, value]) => ({
          criterion_id,
          value,
        })),
        comment,
      });
      setSaved(true);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Save failed.");
    }
  }

  async function handleSubmit() {
    setStatus("submitting");
    setError(null);
    try {
      await handleSave();
      const result = await api.submitScore(projectId);
      setSubmittedAt(result.submitted_at);
      setStatus("idle");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Submit failed.");
    }
  }

  if (submittedAt) {
    return (
      <Alert>
        <CheckCircle2 className="size-4" />
        <AlertDescription className="flex items-center justify-between gap-3">
          <span>Submitted at {new Date(submittedAt).toLocaleString()}.</span>
          <Button variant="outline" size="sm" onClick={() => setSubmittedAt(null)}>
            Edit review
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex max-w-xl flex-col gap-4">
      {criteria.map((criterion) => (
        <Card key={criterion.id}>
          <CardHeader className="flex-row items-baseline justify-between gap-2 space-y-0">
            <span className="font-semibold">{criterion.name}</span>
            <span className="text-xs text-muted-foreground">
              weight {criterion.weight}
            </span>
          </CardHeader>
          <CardContent>
            {criterion.description && (
              <p className="mb-3 text-sm text-muted-foreground">
                {criterion.description}
              </p>
            )}
            <div className="flex items-center gap-3">
              <Slider
                min={criterion.min}
                max={criterion.max}
                step={1}
                value={[values[criterion.id] ?? criterion.min]}
                onValueChange={(v) =>
                  setValue(criterion.id, Array.isArray(v) ? v[0] : v)
                }
                className="flex-1"
              />
              <span className="w-14 text-right text-sm tabular-nums text-muted-foreground">
                {values[criterion.id] ?? criterion.min} / {criterion.max}
              </span>
            </div>
          </CardContent>
        </Card>
      ))}

      <div className="flex flex-col gap-2">
        <Label htmlFor="comment">Comment (optional)</Label>
        <Textarea
          id="comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
        />
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          onClick={handleSave}
          disabled={status === "saving" || status === "submitting"}
        >
          {status === "saving" ? "Saving…" : "Save draft"}
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={status === "saving" || status === "submitting"}
        >
          {status === "submitting" ? "Submitting…" : "Submit review"}
        </Button>
        {saved && status === "idle" && (
          <span className="text-sm font-medium text-success">Saved.</span>
        )}
      </div>
      {status === "error" && error && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
