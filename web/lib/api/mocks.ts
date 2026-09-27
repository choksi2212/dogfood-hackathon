import type {
  AssignmentRunResponse,
  AuditLogResponse,
  BulkInviteResponse,
  CertificateResponse,
  EventDetail,
  GalleryResponse,
  JudgeScoresResponse,
  LoginPayload,
  Membership,
  MyBatchResponse,
  NormalizeResponse,
  PairwiseBallotPayload,
  PairwiseBallotResponse,
  PairwiseRankingResponse,
  RetractVoteResponse,
  ScoreSaveResponse,
  ScoreSubmitResponse,
  SubmissionDetail,
  SubmitPayload,
  SubmitResponse,
  User,
  VoteResponse,
  VoteResultsResponse,
  WidgetGalleryResponse,
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

export async function mockMe(): Promise<User> {
  // Default to "not logged in" — clients should treat a thrown
  // ApiError as the auth gate signal. The /login flow replaces this
  // with a real User.
  throw Object.assign(new Error("not authenticated"), {
    name: "ApiError",
    code: "not_authenticated",
    status: 401,
  }) as Error & { code: string; status: number };
}

export async function mockGallery(): Promise<GalleryResponse> {
  return {
    total: MOCK_SUBMISSIONS.length,
    page: 1,
    page_size: 24,
    items: MOCK_SUBMISSIONS,
  };
}

export async function mockSubmissionDetail(id: string): Promise<SubmissionDetail> {
  // Find the matching mock row, or fall back to the first one so the
  // /gallery/[id] page still renders for unknown IDs in mock mode.
  const row = MOCK_SUBMISSIONS.find((s) => s.id === id) ?? MOCK_SUBMISSIONS[0];
  return {
    ...row,
    description: row.description ?? "Mock fixture standing in until the real backend returns.",
    team: "mock-team",
    team_name: "Mock Team",
    event: "sample-hack-2026",
    track: "mock-track",
    demo_video_url: "",
    repo_url: "",
    live_url: "",
    status: "submitted",
    created_at: row.submitted_at ?? new Date().toISOString(),
    updated_at: row.submitted_at ?? new Date().toISOString(),
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

export async function mockVote(projectId: string): Promise<VoteResponse> {
  return {
    vote_id: `mock-vote-${projectId}`,
    votes: 1,
    mode: "simple",
    spent_credits: null,
  };
}

export async function mockRetractVote(
  projectId: string,
): Promise<RetractVoteResponse> {
  return { retracted: true, vote_id: `mock-vote-${projectId}` };
}

export async function mockPairwiseBallot(
  payload: PairwiseBallotPayload,
): Promise<PairwiseBallotResponse> {
  return {
    ballot_id: "mock-ballot",
    created: true,
    winner: payload.winner,
  };
}

export async function mockEventDetail(): Promise<EventDetail> {
  return {
    id: "mock-event",
    slug: "sample-hack-2026",
    name: "Sample Hack 2026",
    description: "Mock fixture standing in until the real event loads.",
    open_at: "2026-09-20T00:00:00Z",
    submissions_close_at: "2026-09-26T23:00:00Z",
    judging_open_at: "2026-09-26T22:30:00Z",
    judging_close_at: "2026-09-29T00:00:00Z",
    results_at: "2026-09-30T00:00:00Z",
    voting_mode: "simple",
    pairwise_enabled: true,
    tracks: [
      { id: "t1", name: "Main", slug: "main", description: "", order: 0 },
    ],
    prizes: [],
    rubric: {
      id: "r1",
      name: "Default",
      criteria: [
        {
          id: "c1",
          name: "Innovation",
          description: "",
          weight: "0.400",
          min: 1,
          max: 5,
          order: 0,
        },
      ],
    },
    state: "judging",
  };
}

export async function mockMemberships(): Promise<Membership[]> {
  return [
    {
      id: "m1",
      user: "u1",
      user_email: "organizer@dogfood.local",
      user_name: "Olivia Organizer",
      role: "organizer",
      created_at: "2026-09-20T00:00:00Z",
    },
    {
      id: "m2",
      user: "u2",
      user_email: "judge_a@dogfood.local",
      user_name: "Avery Alpha-Judge",
      role: "judge",
      created_at: "2026-09-20T00:00:00Z",
    },
  ];
}

export async function mockBulkInvite(
  emails: string[],
): Promise<BulkInviteResponse> {
  return { invited: emails.filter((e) => e.trim()).length };
}

export async function mockAssignmentRun(): Promise<AssignmentRunResponse> {
  return {
    batch_id: "mock-batch",
    n_assignments: 30,
    judges_with_zero_projects: [],
    seed_used: 42,
    attempts: 1,
  };
}

export async function mockNormalize(): Promise<NormalizeResponse> {
  return {
    run_id: "mock-norm-run",
    raw_sigma: 1.42,
    normalized_sigma: 0.31,
    is_connected: true,
    iterations: 12,
    n_projects: 10,
    n_judges: 4,
    n_reviews: 30,
    proof: "mock proof text",
  };
}

export async function mockMyBatch(): Promise<MyBatchResponse> {
  return {
    projects: [
      { id: "mock-1", name: "Quokka", tagline: "A tiny, friendly submission platform.", submitted: true, reviewed: false },
      { id: "mock-2", name: "Wombat Watch", tagline: "Uptime monitoring with a marsupial mascot.", submitted: true, reviewed: true },
    ],
    progress: { scored: 1, total: 2 },
  };
}

export async function mockScoreSave(): Promise<ScoreSaveResponse> {
  return { saved: true };
}

export async function mockScoreSubmit(): Promise<ScoreSubmitResponse> {
  return { submitted_at: new Date().toISOString() };
}

export async function mockPairwiseRanking(): Promise<PairwiseRankingResponse> {
  return {
    run_id: "mock-run",
    event_slug: "sample-hack-2026",
    n_ballots: 2,
    iterations: 5,
    converged: true,
    ranking: [
      {
        project_id: "mock-1",
        theta: 0.8,
        rank: 1,
        wins: 2,
        losses: 0,
        ties: 0,
      },
      {
        project_id: "mock-2",
        theta: -0.2,
        rank: 2,
        wins: 0,
        losses: 2,
        ties: 0,
      },
    ],
  };
}

export async function mockCertificate(publicId: string): Promise<CertificateResponse> {
  return {
    public_id: publicId,
    submission_id: "mock-1",
    issued_at: "2026-09-27T00:00:00Z",
    signed_payload: {
      submission_id: "mock-1",
      name: "Quokka",
      event_slug: "sample-hack-2026",
    },
    signature: "mockmocksignaturemocksignaturemocksignaturemocksignature",
    signature_algorithm: "HMAC-SHA256",
  };
}

export async function mockWidgetGallery(): Promise<WidgetGalleryResponse> {
  return {
    items: MOCK_SUBMISSIONS.map((s) => ({
      id: s.id,
      name: s.name,
      tagline: s.tagline,
      track_slug: s.track_slug,
    })),
    event: "sample-hack-2026",
  };
}

export async function mockVoteResults(): Promise<VoteResultsResponse> {
  return {
    event_slug: "sample-hack-2026",
    voting_mode: "simple",
    results_visible: true,
    results: [
      { project_id: "mock-1", project_name: "Quokka", vote_count: 3, total_votes: 3 },
      { project_id: "mock-2", project_name: "Wombat Watch", vote_count: 1, total_votes: 1 },
    ],
  };
}

export async function mockAuditLog(): Promise<AuditLogResponse> {
  return {
    event_slug: "sample-hack-2026",
    entries: [
      {
        id: "mock-1",
        actor_email: "participant@dogfood.local",
        action: "vote.cast",
        target_type: "Vote",
        target_id: "mock-vote-1",
        result: "success",
        created_at: "2026-09-27T00:00:00Z",
      },
      {
        id: "mock-2",
        actor_email: null,
        action: "vote.retract",
        target_type: "Vote",
        target_id: "mock-vote-2",
        result: "success",
        created_at: "2026-09-27T00:01:00Z",
      },
    ],
  };
}
