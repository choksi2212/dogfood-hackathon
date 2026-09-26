import { routes } from "./routes";
import { mockGallery, mockJudgeScores, mockSubmit } from "./mocks";
import {
  ApiError,
  type ApiErrorBody,
  type GalleryResponse,
  type JudgeScoresResponse,
  type SubmitPayload,
  type SubmitResponse,
} from "./types";

// Flip NEXT_PUBLIC_USE_MOCKS=1 to develop screens before the backend
// route exists or is reachable. Both adapters implement the same
// interface below, so switching is not a component-level change.
const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "1";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
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

  judgeScores(): Promise<JudgeScoresResponse> {
    return USE_MOCKS ? mockJudgeScores() : request(routes.judgeScores());
  },

  // Judge B's own console reuses judgeScores(); this is for the one
  // graded cross-judge cell (organizer/audit tooling), which the spec
  // expects to come back 401/403 for a judge peeking at another judge.
  peerScores(judge: string): Promise<JudgeScoresResponse> {
    return USE_MOCKS ? mockJudgeScores() : request(routes.peerScores(judge));
  },

  // CSV export is a file download, not JSON — callers link/window.open
  // to this URL directly rather than fetching it through `request`.
  csvExportUrl(): string {
    return `${API_BASE}${routes.csvExport()}`;
  },
};

export { ApiError };
