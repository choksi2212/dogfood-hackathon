import { routes } from "./routes";
import {
  ApiError,
  type ApiErrorBody,
  type AssignmentRunResponse,
  type AuditLogResponse,
  type BulkInviteResponse,
  type CertificateResponse,
  type EventDetail,
  type GalleryResponse,
  type JudgeScoresResponse,
  type LoginPayload,
  type Membership,
  type MyBatchResponse,
  type NormalizeResponse,
  type PairwiseBallotPayload,
  type PairwiseBallotResponse,
  type PairwiseRankingResponse,
  type RetractVoteResponse,
  type RubricResponse,
  type ScoreSavePayload,
  type ScoreSaveResponse,
  type ScoreSubmitResponse,
  type SubmissionDetail,
  type SubmitPayload,
  type SubmitResponse,
  type User,
  type VoteResponse,
  type VoteResultsResponse,
  type WidgetGalleryResponse,
} from "./types";

// Server Components run on the Node server and can reach Django
// directly — no browser involved, so no CORS concern. Client Components
// run in the browser, where a direct cross-origin call to the backend
// would need CORS and complicate cookie handling; instead they call a
// relative /api/* path on this same origin, which next.config.ts
// rewrites to the backend server-side (same trick nginx plays in
// production, see docs/TRD.md §8.2).
const API_BASE =
  typeof window === "undefined"
    ? (process.env.API_INTERNAL_URL ?? "http://localhost:8001")
    : "";

// widget.js is meant to be <script>-embedded on third-party sites, so
// unlike everything else here it needs a URL the *browser* can reach
// directly — not the server-only API_INTERNAL_URL, and not proxied
// through next.config.ts either, since the whole point is other sites
// loading it cross-origin (it ships its own CORS: * for that reason).
const WIDGET_BASE =
  process.env.NEXT_PUBLIC_WIDGET_BASE ?? "http://localhost:8001";

function cookieInit(cookieHeader?: string): RequestInit | undefined {
  return cookieHeader ? { headers: { Cookie: cookieHeader } } : undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    // Matters only in the browser (relative URL, same origin). A
    // server-side call passes its own Cookie header explicitly — see
    // `cookieHeader` below — since Server Component fetches don't
    // automatically inherit the incoming request's cookies.
    credentials: "include",
    cache: "no-store",
  });

  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiError(
      res.status,
      body?.error?.code ?? "unknown_error",
      body?.error?.message ?? `Request to ${path} failed with ${res.status}`,
    );
  }

  return res.json() as Promise<T>;
}

export const api = {
  gallery(): Promise<GalleryResponse> {
    return request(routes.gallery());
  },

  me(cookieHeader?: string): Promise<User> {
    return request(routes.me(), cookieInit(cookieHeader));
  },

  submission(id: string): Promise<SubmissionDetail> {
    return request(routes.submission(id));
  },

  submit(payload: SubmitPayload, slug?: string): Promise<SubmitResponse> {
    return request(routes.submit(slug), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  login(payload: LoginPayload): Promise<User> {
    return request(routes.login(), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // 204 No Content on success — bypasses `request`'s unconditional
  // `res.json()` since there's no body to parse.
  async logout(): Promise<void> {
    const res = await fetch(routes.logout(), {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as ApiErrorBody | null;
      throw new ApiError(
        res.status,
        body?.error?.code ?? "unknown_error",
        body?.error?.message ?? `Logout failed with ${res.status}`,
      );
    }
  },

  // `cookieHeader` is required when called from a Server Component —
  // pass the incoming request's `Cookie` header (via next/headers) so
  // the backend sees the visitor's session. Browser (Client Component)
  // callers can omit it; `credentials: "include"` on `request` handles
  // that case instead.
  judgeScores(cookieHeader?: string): Promise<JudgeScoresResponse> {
    return request(routes.judgeScores(), cookieInit(cookieHeader));
  },

  // Judge B's own console reuses judgeScores(); this is for the one
  // graded cross-judge cell (organizer/audit tooling), which the spec
  // expects to come back 401/403 for a judge peeking at another judge.
  peerScores(judge: string, cookieHeader?: string): Promise<JudgeScoresResponse> {
    return request(routes.peerScores(judge), cookieInit(cookieHeader));
  },

  // Casting is anonymous-friendly (AllowAny on the backend) — an
  // authenticated voter is identified by session cookie same as
  // everywhere else, an anonymous one by IP+UA fingerprint server-side.
  vote(projectId: string, slug?: string): Promise<VoteResponse> {
    return request(routes.vote(projectId, slug), { method: "POST" });
  },

  retractVote(projectId: string, slug?: string): Promise<RetractVoteResponse> {
    return request(routes.vote(projectId, slug), { method: "DELETE" });
  },

  pairwiseBallot(
    payload: PairwiseBallotPayload,
    slug?: string,
  ): Promise<PairwiseBallotResponse> {
    return request(routes.pairwiseBallots(slug), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  pairwiseRanking(
    slug?: string,
    cookieHeader?: string,
  ): Promise<PairwiseRankingResponse> {
    return request(routes.pairwiseRanking(slug), cookieInit(cookieHeader));
  },

  // Organizer dashboard. eventDetail/memberships are read from a
  // Server Component (cookie forwarded like judgeScores); the action
  // endpoints are triggered from a Client Component so they need no
  // explicit cookie (same-origin browser request, credentials:
  // "include" on `request` covers it).
  eventDetail(slug?: string, cookieHeader?: string): Promise<EventDetail> {
    return request(routes.eventDetail(slug), cookieInit(cookieHeader));
  },

  // Rubric-only read, split out from eventDetail. Judges hit this from
  // the scoring console to label their sliders; organizers and
  // participants can read it too. Returns the same `rubric` shape
  // EventDetail.rubric had — just without prizes / judging window /
  // voting mode, which are organizer-only on EventDetailView.
  rubric(slug?: string, cookieHeader?: string): Promise<RubricResponse> {
    return request(routes.rubric(slug), cookieInit(cookieHeader));
  },

  memberships(slug?: string, cookieHeader?: string): Promise<Membership[]> {
    return request(routes.memberships(slug), cookieInit(cookieHeader));
  },

  bulkInviteJudges(emails: string[], slug?: string): Promise<BulkInviteResponse> {
    return request(routes.bulkInviteJudges(slug), {
      method: "POST",
      body: JSON.stringify({ emails }),
    });
  },

  runAssignment(
    payload: { seed?: number; reviews_per_project?: number } = {},
    slug?: string,
  ): Promise<AssignmentRunResponse> {
    return request(routes.assignmentsRun(slug), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  runNormalization(slug?: string): Promise<NormalizeResponse> {
    return request(routes.normalize(slug), { method: "POST" });
  },

  // Judge console — real project names/tagline, unlike judgeScores()
  // above which only has bare UUIDs.
  meBatch(slug?: string, cookieHeader?: string): Promise<MyBatchResponse> {
    return request(routes.meBatch(slug), cookieInit(cookieHeader));
  },

  saveScore(
    projectId: string,
    payload: ScoreSavePayload,
    slug?: string,
  ): Promise<ScoreSaveResponse> {
    return request(routes.scoreSave(projectId, slug), {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  submitScore(projectId: string, slug?: string): Promise<ScoreSubmitResponse> {
    return request(routes.scoreSubmit(projectId, slug), { method: "POST" });
  },

  // Public, no auth — a certificate is a signed record anyone holding
  // the public_id can verify.
  certificate(publicId: string): Promise<CertificateResponse> {
    return request(routes.certificate(publicId));
  },

  // Widget preview data, fetched the same way a third-party embedder's
  // browser would (direct cross-origin GET, no cookies) — not proxied,
  // to demonstrate the real embed actually works standalone.
  widgetGallery(slug?: string): Promise<WidgetGalleryResponse> {
    return fetch(`${WIDGET_BASE}${routes.widgetGallery(slug)}`, {
      credentials: "omit",
      cache: "no-store",
    }).then((res) => res.json() as Promise<WidgetGalleryResponse>);
  },

  widgetScriptUrl(): string {
    return `${WIDGET_BASE}/widget.js`;
  },

  // Organizer-only. Both endpoints were missing entirely until now —
  // apps/voting only had cast/retract, and apps/audit had no HTTP
  // surface at all despite writing AuditEvent rows across the app.
  voteResults(slug?: string, cookieHeader?: string): Promise<VoteResultsResponse> {
    return request(routes.voteResults(slug), cookieInit(cookieHeader));
  },

  auditLog(
    slug?: string,
    limit?: number,
    cookieHeader?: string,
  ): Promise<AuditLogResponse> {
    return request(routes.auditLog(slug, limit), cookieInit(cookieHeader));
  },

  // CSV export is a file download the browser navigates to directly
  // (an <a href>), even when this is called during a Server Component
  // render — so unlike `request`, it always returns the browser-facing
  // relative path (proxied by next.config.ts rewrites), never the
  // server-only internal URL.
  csvExportUrl(): string {
    return routes.csvExport();
  },
};

export { ApiError };
