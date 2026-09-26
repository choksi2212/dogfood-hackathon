import type {
  GalleryResponse,
  JudgeScoresResponse,
  LoginPayload,
  SubmitPayload,
  SubmitResponse,
  User,
} from "./types";

const MOCK_SUBMISSIONS: GalleryResponse["items"] = [
  {
    id: "mock-1",
    name: "Quokka",
    tagline: "A tiny, friendly submission platform.",
    description: "Mock fixture standing in until the real gallery loads.",
    track_slug: "main",
    thumbnail_path: null,
    submitted_at: "2026-09-27T00:00:00Z",
  },
  {
    id: "mock-2",
    name: "Wombat Watch",
    tagline: "Uptime monitoring with a marsupial mascot.",
    description: "Second mock fixture so empty-state and list-state both render.",
    track_slug: "main",
    thumbnail_path: null,
    submitted_at: "2026-09-27T01:00:00Z",
  },
];

const MOCK_JUDGE_SCORES: JudgeScoresResponse = {
  judge_id: "mock-judge-a",
  scores: [
    {
      project_id: "mock-1",
      criterion_id: "mock-criterion-innovation",
      value: 4,
      updated_at: "2026-09-27T00:00:00Z",
    },
  ],
};

export async function mockGallery(): Promise<GalleryResponse> {
  return {
    total: MOCK_SUBMISSIONS.length,
    page: 1,
    page_size: 24,
    items: MOCK_SUBMISSIONS,
  };
}

export async function mockSubmit(
  payload: SubmitPayload,
): Promise<SubmitResponse> {
  return {
    id: "mock-new",
    name: payload.name ?? "Untitled submission",
    tagline: payload.tagline ?? "",
    description: payload.description ?? "",
    track_slug: payload.track_slug ?? "main",
    thumbnail_path: null,
    submitted_at: new Date().toISOString(),
    team: "mock-team",
    team_name: "Mock Team",
    event: "sample-hack-2026",
    track: "mock-track",
    demo_video_url: "",
    repo_url: "",
    live_url: "",
    status: "submitted",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export async function mockJudgeScores(): Promise<JudgeScoresResponse> {
  return MOCK_JUDGE_SCORES;
}

export async function mockLogin(payload: LoginPayload): Promise<User> {
  return {
    id: "mock-user",
    email: payload.email,
    name: "Mock User",
    is_active: true,
    memberships: [{ event: "sample-hack-2026", role: "participant" }],
  };
}
