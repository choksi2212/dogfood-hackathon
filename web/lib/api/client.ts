import { routes } from "./routes";
import {
  mockAssignmentRun,
  mockBulkInvite,
  mockEventDetail,
  mockGallery,
  mockJudgeScores,
  mockLogin,
  mockMemberships,
  mockNormalize,
  mockPairwiseBallot,
  mockPairwiseRanking,
  mockRetractVote,
  mockSubmit,
  mockVote,
} from "./mocks";
import {
  ApiError,
  type ApiErrorBody,
  type AssignmentRunResponse,
  type BulkInviteResponse,
  type EventDetail,
  type GalleryResponse,
  type JudgeScoresResponse,
  type LoginPayload,
  type Membership,
  type NormalizeResponse,
  type PairwiseBallotPayload,
  type PairwiseBallotResponse,
  type PairwiseRankingResponse,
  type RetractVoteResponse,
  type SubmitPayload,
  type SubmitResponse,
  type User,
  type VoteResponse,
} from "./types";

// Flip NEXT_PUBLIC_USE_MOCKS=1 to develop screens before the backend
// route exists or is reachable. Both adapters implement the same
// interface below, so switching is not a component-level change.
const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "1";

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
    return USE_MOCKS ? mockGallery() : request(routes.gallery());
  },

  submit(payload: SubmitPayload, slug?: string): Promise<SubmitResponse> {
    return USE_MOCKS
      ? mockSubmit(payload)
      : request(routes.submit(slug), {
          method: "POST",
          body: JSON.stringify(payload),
        });
  },

  login(payload: LoginPayload): Promise<User> {
    return USE_MOCKS
      ? mockLogin(payload)
      : request(routes.login(), {
          method: "POST",
          body: JSON.stringify(payload),
        });
  },

  // `cookieHeader` is required when called from a Server Component —
  // pass the incoming request's `Cookie` header (via next/headers) so
  // the backend sees the visitor's session. Browser (Client Component)
  // callers can omit it; `credentials: "include"` on `request` handles
  // that case instead.
  judgeScores(cookieHeader?: string): Promise<JudgeScoresResponse> {
    return USE_MOCKS
      ? mockJudgeScores()
      : request(routes.judgeScores(), cookieInit(cookieHeader));
  },

  // Judge B's own console reuses judgeScores(); this is for the one
  // graded cross-judge cell (organizer/audit tooling), which the spec
  // expects to come back 401/403 for a judge peeking at another judge.
  peerScores(judge: string, cookieHeader?: string): Promise<JudgeScoresResponse> {
    return USE_MOCKS
      ? mockJudgeScores()
      : request(routes.peerScores(judge), cookieInit(cookieHeader));
  },

  // Casting is anonymous-friendly (AllowAny on the backend) — an
  // authenticated voter is identified by session cookie same as
  // everywhere else, an anonymous one by IP+UA fingerprint server-side.
  vote(projectId: string, slug?: string): Promise<VoteResponse> {
    return USE_MOCKS
      ? mockVote(projectId)
      : request(routes.vote(projectId, slug), { method: "POST" });
  },

  retractVote(projectId: string, slug?: string): Promise<RetractVoteResponse> {
    return USE_MOCKS
      ? mockRetractVote(projectId)
      : request(routes.vote(projectId, slug), { method: "DELETE" });
  },

  pairwiseBallot(
    payload: PairwiseBallotPayload,
    slug?: string,
  ): Promise<PairwiseBallotResponse> {
    return USE_MOCKS
      ? mockPairwiseBallot(payload)
      : request(routes.pairwiseBallots(slug), {
          method: "POST",
          body: JSON.stringify(payload),
        });
  },

  pairwiseRanking(
    slug?: string,
    cookieHeader?: string,
  ): Promise<PairwiseRankingResponse> {
    return USE_MOCKS
      ? mockPairwiseRanking()
      : request(routes.pairwiseRanking(slug), cookieInit(cookieHeader));
  },

  // Organizer dashboard. eventDetail/memberships are read from a
  // Server Component (cookie forwarded like judgeScores); the action
  // endpoints are triggered from a Client Component so they need no
  // explicit cookie (same-origin browser request, credentials:
  // "include" on `request` covers it).
  eventDetail(slug?: string, cookieHeader?: string): Promise<EventDetail> {
    return USE_MOCKS
      ? mockEventDetail()
      : request(routes.eventDetail(slug), cookieInit(cookieHeader));
  },

  memberships(slug?: string, cookieHeader?: string): Promise<Membership[]> {
    return USE_MOCKS
      ? mockMemberships()
      : request(routes.memberships(slug), cookieInit(cookieHeader));
  },

  bulkInviteJudges(emails: string[], slug?: string): Promise<BulkInviteResponse> {
    return USE_MOCKS
      ? mockBulkInvite(emails)
      : request(routes.bulkInviteJudges(slug), {
          method: "POST",
          body: JSON.stringify({ emails }),
        });
  },

  runAssignment(
    payload: { seed?: number; reviews_per_project?: number } = {},
    slug?: string,
  ): Promise<AssignmentRunResponse> {
    return USE_MOCKS
      ? mockAssignmentRun()
      : request(routes.assignmentsRun(slug), {
          method: "POST",
          body: JSON.stringify(payload),
        });
  },

  runNormalization(slug?: string): Promise<NormalizeResponse> {
    return USE_MOCKS
      ? mockNormalize()
      : request(routes.normalize(slug), { method: "POST" });
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
