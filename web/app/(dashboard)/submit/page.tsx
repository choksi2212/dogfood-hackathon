"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
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

type Status = "idle" | "loading" | "success" | "error";

const KNOWN_TRACKS = [
  { slug: "main", label: "Main" },
  { slug: "wildcard", label: "Wildcard" },
];

export default function SubmitPage() {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    tagline: "",
    description: "",
    repo_url: "",
    live_url: "",
    demo_video_url: "",
    track_slug: KNOWN_TRACKS[0].slug,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage(null);
    try {
      const created = await api.submit(form);
      // Don't leave the user on a static "received" page — they want
      // to see their submission in the gallery right away.
      router.push(`/gallery/${created.id}`);
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof ApiError ? err.message : "Something went wrong.",
      );
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Submit your project</h1>
      <p className="mt-1 text-muted-foreground">
        Tell judges what you built — you can edit this until submissions close.
      </p>
      <form className="mt-6 flex max-w-lg flex-col gap-4" onSubmit={handleSubmit}>
        <div className="flex flex-col gap-2">
          <Label htmlFor="name">Project name</Label>
          <Input
            id="name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            maxLength={80}
            required
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="tagline">Tagline</Label>
          <Input
            id="tagline"
            value={form.tagline}
            onChange={(e) => setForm({ ...form, tagline: e.target.value })}
            maxLength={140}
            placeholder="One sentence — what's the hook?"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={6}
            maxLength={8000}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="track">Track</Label>
          <Select
            value={form.track_slug}
            onValueChange={(v) => v && setForm({ ...form, track_slug: v })}
          >
            <SelectTrigger id="track" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {KNOWN_TRACKS.map((t) => (
                <SelectItem key={t.slug} value={t.slug}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="repo_url">Source repo (optional)</Label>
          <Input
            id="repo_url"
            type="url"
            value={form.repo_url}
            onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
            placeholder="https://github.com/team/project"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="live_url">Live site (optional)</Label>
          <Input
            id="live_url"
            type="url"
            value={form.live_url}
            onChange={(e) => setForm({ ...form, live_url: e.target.value })}
            placeholder="https://example.com"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="demo_video_url">Demo video (optional)</Label>
          <Input
            id="demo_video_url"
            type="url"
            value={form.demo_video_url}
            onChange={(e) => setForm({ ...form, demo_video_url: e.target.value })}
            placeholder="https://youtu.be/…"
          />
        </div>
        <Button type="submit" disabled={status === "loading"} className="self-start">
          {status === "loading" ? "Submitting…" : "Submit"}
        </Button>
        {status === "error" && errorMessage && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        )}
      </form>
    </div>
  );
}
