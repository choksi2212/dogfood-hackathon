"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  Check,
  Save,
  Rocket,
  Link2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageHeading } from "@/components/portal-ui";
import { useHydrated } from "@/hooks/use-hydrated";

const emptyForm = {
  name: "",
  tagline: "",
  description: "",
  repo_url: "",
  live_url: "",
  demo_video_url: "",
  track_slug: "",
};
type ProjectForm = typeof emptyForm;

export function SubmitForm({ draftKey }: { draftKey: string }) {
  const router = useRouter();
  const hydrated = useHydrated();
  const [editedForm, setForm] = useState<ProjectForm | null>(null);
  const restoredForm = useMemo(() => {
    if (!hydrated) return emptyForm;
    try {
      const stored = localStorage.getItem(draftKey);
      const parsed: unknown = stored ? JSON.parse(stored) : null;
      const restored = { ...emptyForm };
      if (typeof parsed === "object" && parsed !== null) {
        for (const key of Object.keys(restored) as (keyof ProjectForm)[]) {
          const value = (parsed as Record<string, unknown>)[key];
          if (typeof value === "string") restored[key] = value;
        }
      }
      return restored;
    } catch {
      return emptyForm;
    }
  }, [hydrated, draftKey]);
  const form = editedForm ?? restoredForm;
  const [loading, setLoading] = useState(false);
  const [draftSaved, setDraftSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tracks, setTracks] = useState<{ slug: string; label: string }[]>([]);
  const [trackError, setTrackError] = useState(false);
  const [trackRetry, setTrackRetry] = useState(0);
  useEffect(() => {
    let active = true;
    api
      .allGallery()
      .then((items) => {
        if (!active) return;
        const slugs = Array.from(
          new Set(items.map((item) => item.track_slug)),
        ).sort();
        setTracks(
          slugs.map((slug) => ({
            slug,
            label: slug
              .split("-")
              .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
              .join(" "),
          })),
        );
      })
      .catch(() => {
        if (active) setTrackError(true);
      });
    return () => {
      active = false;
    };
  }, [trackRetry]);
  function update(key: keyof ProjectForm, value: string) {
    setForm((prev) => ({ ...(prev ?? restoredForm), [key]: value }));
    setDraftSaved(false);
  }
  function saveDraft() {
    try {
      localStorage.setItem(draftKey, JSON.stringify(form));
      setDraftSaved(true);
      setError(null);
    } catch {
      setError(
        "This browser couldn’t save your draft. Keep this page open and try again.",
      );
    }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.submit(form);
      try {
        localStorage.setItem(draftKey, JSON.stringify(form));
      } catch {
        /* Submission already succeeded. */
      }
      router.push(`/gallery/${result.id}`);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Your project couldn’t be submitted. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div>
      <PageHeading
        eyebrow="PARTICIPANT / THE BIG REVEAL"
        title="Submit your project"
        description="A good idea deserves a great introduction. Tell the judges the story behind your project."
      />
      <form onSubmit={submit} className="space-y-6">
        <div className="grid items-start gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section className="surface p-6 sm:p-8">
            <div className="mb-7 flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-accent-dim text-accent">
                <Rocket className="size-5" />
              </span>
              <div>
                <h2 className="text-lg font-medium tracking-tight">
                  The project
                </h2>
                <p className="mt-1 text-xs text-text-muted">
                  Make the first impression count.
                </p>
              </div>
            </div>
            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="project-name">
                  Project name <span className="text-accent">*</span>
                </Label>
                <Input
                  id="project-name"
                  value={form.name}
                  onChange={(e) => update("name", e.target.value)}
                  maxLength={80}
                  required
                  placeholder="Give your idea a name"
                />
                <p className="text-right font-mono text-xs text-text-muted">
                  {form.name.length}/80
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-tagline">The one-line pitch</Label>
                <Input
                  id="project-tagline"
                  value={form.tagline}
                  onChange={(e) => update("tagline", e.target.value)}
                  maxLength={140}
                  placeholder="What does it do, and why does it matter?"
                />
                <p className="text-right font-mono text-xs text-text-muted">
                  {form.tagline.length}/140
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-description">Tell the story</Label>
                <Textarea
                  id="project-description"
                  value={form.description}
                  onChange={(e) => update("description", e.target.value)}
                  rows={9}
                  maxLength={8000}
                  placeholder="The problem you chose. The solution you built. The details you’re proud of."
                />
                <p className="text-xs leading-relaxed text-text-muted">
                  Share what works today, what you learned, and what comes next.
                </p>
              </div>
            </div>
          </section>
          <div className="space-y-6">
            <section className="surface p-6">
              <p className="eyebrow mb-5">Find your lane</p>
              <div className="space-y-2">
                <Label htmlFor="project-track">Track</Label>
                <Select
                  value={form.track_slug}
                  onValueChange={(value) =>
                    value !== null && update("track_slug", value)
                  }
                >
                  <SelectTrigger id="project-track" className="w-full">
                    <SelectValue>
                      {tracks.find((track) => track.slug === form.track_slug)
                        ?.label ?? "Default event track"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Default event track</SelectItem>
                    {tracks.map((track) => (
                      <SelectItem key={track.slug} value={track.slug}>
                        {track.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-text-muted">
                Choose from tracks in the gallery, or use the event’s default
                track.
              </p>
              {trackError && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setTrackError(false);
                    setTrackRetry((value) => value + 1);
                  }}
                >
                  Reload track options
                </Button>
              )}
            </section>
            <section className="surface p-6">
              <div className="mb-5 flex items-center gap-2">
                <Link2 className="size-4 text-accent" />
                <h2 className="font-medium">Project links</h2>
                <span className="ml-auto rounded-full bg-bg-overlay px-2 py-1 text-xs text-text-muted">
                  Optional
                </span>
              </div>
              <p className="mb-5 text-xs leading-relaxed text-text-secondary">
                Keep these links in your local draft. Link publishing isn’t
                available for this event.
              </p>
              <div className="space-y-4">
                {[
                  {
                    key: "repo_url" as const,
                    label: "Source repository",
                    placeholder: "https://github.com/your-team/project",
                  },
                  {
                    key: "live_url" as const,
                    label: "Live project",
                    placeholder: "https://your-project.com",
                  },
                  {
                    key: "demo_video_url" as const,
                    label: "Demo video",
                    placeholder: "https://youtu.be/…",
                  },
                ].map((field) => (
                  <div key={field.key} className="space-y-2">
                    <Label htmlFor={field.key}>{field.label}</Label>
                    <Input
                      id={field.key}
                      type="url"
                      value={form[field.key]}
                      onChange={(e) => update(field.key, e.target.value)}
                      placeholder={field.placeholder}
                    />
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-bg-elevated px-6 py-5">
          <div aria-live="polite">
            <p className="text-sm font-medium">
              {draftSaved
                ? "Draft saved on this device."
                : "Your next big thing is almost ready."}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Drafts are private to this browser. Submit to publish in the
              gallery.
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={saveDraft}
              disabled={loading}
            >
              {draftSaved ? (
                <Check className="size-4 text-success" />
              ) : (
                <Save className="size-4" />
              )}
              Save draft
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <ArrowUpRight className="size-4" />
              )}
              {loading ? "Submitting…" : "Submit project"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
