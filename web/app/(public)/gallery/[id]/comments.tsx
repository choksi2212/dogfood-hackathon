"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { EyeOff, Loader2, MessageCircle, SendHorizontal } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import type { Comment, User } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RouteError } from "@/components/route-error";
import { cn } from "@/lib/cn";

const MAX_COMMENT_LENGTH = 2000;

// The comment API is PII-safe by design — it never returns names or
// emails, only a stable truncated email hash. So the gallery shows a
// consistent anonymous handle per person ("member 3b0e4a6b…"), and
// reveals the real name only for comments the visitor wrote
// themselves (we have it from /api/me).
function authorLabel(comment: Comment, me: User | null): string {
  if (me && comment.author && comment.author === me.id) return me.name;
  if (comment.author_email_hash)
    return `member ${comment.author_email_hash.slice(0, 8)}`;
  return "removed member";
}

function authorInitials(comment: Comment, label: string): string {
  if (comment.author_email_hash)
    return comment.author_email_hash.slice(0, 2).toUpperCase();
  return label.slice(0, 2).toUpperCase();
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  const units: [number, string][] = [
    [31557600, "year"],
    [2629800, "month"],
    [604800, "week"],
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
  ];
  for (const [size, unit] of units) {
    if (seconds >= size) {
      const value = Math.floor(seconds / size);
      return `${value} ${unit}${value === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}

export function CommentsSection({ submissionId }: { submissionId: string }) {
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [body, setBody] = useState("");
  const [posting, setPosting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [posted, setPosted] = useState(false);
  const [hiding, setHiding] = useState<Record<string, boolean>>({});
  const [hideErrors, setHideErrors] = useState<Record<string, string>>({});
  const busy = useRef(new Set<string>());

  useEffect(() => {
    let active = true;
    api
      .comments(submissionId)
      .then((data) => {
        if (active) setComments(data);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    // 401 for anonymous visitors just means "read-only" — no console
    // noise, we simply leave `me` null and hide the composer.
    api
      .me()
      .then((user) => {
        if (active) setMe(user);
      })
      .catch(() => {
        if (active) setMe(null);
      });
    return () => {
      active = false;
    };
  }, [retry, submissionId]);

  // Organizers moderate via PATCH …/comments/<id> (apps/submissions
  // CommentModerateView); every other role gets a read/post-only UI.
  const isOrganizer = Boolean(
    me?.memberships.some(
      (membership) =>
        membership.event === EVENT_SLUG && membership.role === "organizer",
    ),
  );

  async function post(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) {
      setFormError("Write a comment before posting.");
      return;
    }
    setPosting(true);
    setFormError(null);
    try {
      const created = await api.postComment(submissionId, trimmed);
      setComments((prev) => [...(prev ?? []), created]);
      setBody("");
      setPosted(true);
    } catch (err) {
      setPosted(false);
      setFormError(
        err instanceof ApiError
          ? err.message
          : "Your comment couldn’t be posted. Please try again.",
      );
    } finally {
      setPosting(false);
    }
  }

  async function hide(commentId: string) {
    if (busy.current.has(commentId)) return;
    busy.current.add(commentId);
    setHiding((prev) => ({ ...prev, [commentId]: true }));
    setHideErrors((prev) => ({ ...prev, [commentId]: "" }));
    try {
      await api.moderateComment(submissionId, commentId, "hide");
      setComments((prev) => (prev ?? []).filter((c) => c.id !== commentId));
    } catch (err) {
      setHideErrors((prev) => ({
        ...prev,
        [commentId]:
          err instanceof ApiError
            ? err.message
            : "This comment couldn’t be hidden. Please try again.",
      }));
    } finally {
      busy.current.delete(commentId);
      setHiding((prev) => ({ ...prev, [commentId]: false }));
    }
  }

  return (
    <section
      aria-labelledby="comments-heading"
      className="mt-10 rounded-2xl border border-border bg-bg-elevated p-7 sm:p-9"
    >
      <div className="mb-6 flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent-dim text-accent">
          <MessageCircle className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="eyebrow">COMMUNITY / JOIN THE CONVERSATION</p>
          <h2 id="comments-heading" className="text-2xl font-medium tracking-tight">
            Comments
          </h2>
        </div>
        {comments && comments.length > 0 && (
          <span className="ml-auto rounded-full bg-bg-overlay px-3 py-1 font-mono text-xs text-text-muted">
            {comments.length}
          </span>
        )}
      </div>

      {failed ? (
        <RouteError
          message="Could not load comments"
          reset={() => {
            setFailed(false);
            setComments(null);
            setRetry((value) => value + 1);
          }}
        />
      ) : !comments ? (
        <div
          role="status"
          className="flex items-center gap-3 rounded-xl border border-dashed border-border p-5 text-sm text-text-muted"
        >
          <Loader2 className="size-4 animate-spin text-accent" />
          Loading comments…
        </div>
      ) : comments.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-5 text-sm leading-relaxed text-text-muted">
          No comments yet. Be the first to share what stood out about this
          build.
        </p>
      ) : (
        <ul className="space-y-5">
          {comments.map((comment) => {
            const label = authorLabel(comment, me);
            const own = Boolean(me && comment.author && comment.author === me.id);
            return (
              <li
                key={comment.id}
                className="rounded-xl border border-border bg-bg p-5"
              >
                <div className="flex items-start gap-4">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-9 shrink-0 items-center justify-center rounded-lg font-mono text-xs",
                      own
                        ? "bg-accent text-white"
                        : "bg-accent-dim text-accent",
                    )}
                  >
                    {authorInitials(comment, label)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="text-sm font-medium">{label}</span>
                      {own && (
                        <span className="rounded-full bg-accent-dim px-2 py-0.5 text-[0.65rem] font-medium text-accent">
                          you
                        </span>
                      )}
                      <time
                        dateTime={comment.created_at}
                        title={new Date(comment.created_at).toLocaleString()}
                        className="font-mono text-xs text-text-muted"
                      >
                        {timeAgo(comment.created_at)}
                      </time>
                    </div>
                    <p className="mt-2 leading-relaxed whitespace-pre-line text-text-secondary">
                      {comment.body}
                    </p>
                    {hideErrors[comment.id] && (
                      <p
                        role="alert"
                        className="mt-2 text-xs leading-relaxed text-error"
                      >
                        {hideErrors[comment.id]}
                      </p>
                    )}
                  </div>
                  {isOrganizer && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      onClick={() => hide(comment.id)}
                      disabled={hiding[comment.id]}
                      aria-label={`Hide comment by ${label}`}
                      className="text-text-muted hover:text-error"
                    >
                      {hiding[comment.id] ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <EyeOff className="size-3" />
                      )}
                      Hide
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {me ? (
        <form onSubmit={post} className="mt-7 space-y-3">
          <Label htmlFor="comment-body">Add a comment</Label>
          <Textarea
            id="comment-body"
            value={body}
            onChange={(e) => {
              setBody(e.target.value);
              setPosted(false);
            }}
            rows={3}
            maxLength={MAX_COMMENT_LENGTH}
            placeholder="Share what stood out about this project…"
            disabled={posting}
            aria-invalid={formError ? true : undefined}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div aria-live="polite" className="text-xs">
              {formError ? (
                <p role="alert" className="text-error">
                  {formError}
                </p>
              ) : posted ? (
                <p className="text-success">Comment posted — thanks for joining in.</p>
              ) : (
                <p className="font-mono text-text-muted">
                  {body.length}/{MAX_COMMENT_LENGTH}
                </p>
              )}
            </div>
            <Button type="submit" disabled={posting}>
              {posting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <SendHorizontal className="size-4" />
              )}
              {posting ? "Posting…" : "Post comment"}
            </Button>
          </div>
        </form>
      ) : (
        <div className="mt-7 flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-border p-5 text-sm text-text-secondary">
          <MessageCircle className="size-4 text-accent" />
          <span>
            Reading is open to everyone —{" "}
            <Link href="/login" className="font-medium text-accent hover:underline">
              log in
            </Link>{" "}
            to add a comment.
          </span>
        </div>
      )}
    </section>
  );
}
