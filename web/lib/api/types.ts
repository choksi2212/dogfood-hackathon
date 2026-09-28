export type Submission = {
  id: string;
  name: string;
  tagline: string;
  description?: string;
  track_slug: string;
  thumbnail_path: string | null;
  submitted_at: string | null;
};

// Matches apps/submissions/views.py GalleryView. Default mode is
// cursor-based ({items, next, page_size}); passing ?page=N switches to
// the legacy offset mode ({total, page, page_size, items}). The
// frontend only ever reads `.items`, so this union covers both shapes
// honestly without the client needing to branch on which one it got.
export type GalleryResponse = {
  items: Submission[];
  page_size: number;
  next?: string | null;
  total?: number;
  page?: number;
};

// Matches apps/submissions/views.py SubmissionDetailView — single
// project read. Adds team + track relations, link URLs, and timestamps
// on top of the gallery row shape.
export type SubmissionDetail = Submission & {
  team: string;
  team_name: string;
  event: string;
  track: string;
  repo_url: string;
  live_url: string;
  demo_video_url: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SubmitPayload = {
  name?: string;
  tagline?: string;
  description?: string;
  track_slug?: string;
  team_id?: string;
};

export type SubmitResponse = Submission & {
  team: string;
  team_name: string;
  event: string;
  track: string;
  demo_video_url: string;
  repo_url: string;
  live_url: string;
  status: string;
  created_at: string;
  updated_at: string;
};

// Matches apps/judging/views.py JudgeScoresView — raw per-criterion
// values, no denormalized names. The console resolves project/criterion
// names once batch endpoints (MyBatchView) are wired in.
export type JudgeScore = {
  project_id: string;
  criterion_id: string;
  value: number;
  updated_at: string;
};

export type JudgeScoresResponse = {
  judge_id: string;
  scores: JudgeScore[];
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
  };
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type User = {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  memberships: { event: string; role: string }[];
};

// Matches apps/voting/views.py VoteView.post response.
export type VoteResponse = {
  vote_id: string;
  votes: number;
  mode: "simple" | "quadratic";
  spent_credits: number | null;
};

export type RetractVoteResponse = {
  retracted: boolean;
  vote_id?: string;
  already?: boolean;
};

// Matches apps/pairwise/views.py.
export type PairwiseWinner = "left" | "right" | "tie";

export type PairwiseBallotPayload = {
  left_id: string;
  right_id: string;
  winner: PairwiseWinner;
};

export type PairwiseBallotResponse = {
  ballot_id: string;
  created: boolean;
  winner: PairwiseWinner;
};

export type PairwiseRankingEntry = {
  project_id: string;
  theta: number;
  rank: number;
  wins: number;
  losses: number;
  ties: number;
};

export type PairwiseRankingResponse = {
  run_id: string;
  event_slug: string;
  n_ballots: number;
  iterations: number;
  converged: boolean;
  ranking: PairwiseRankingEntry[];
};

// Matches apps/events/serializers.py EventSerializer.
export type EventDetail = {
  id: string;
  slug: string;
  name: string;
  description: string;
  open_at: string;
  submissions_close_at: string;
  judging_open_at: string;
  judging_close_at: string;
  results_at: string | null;
  voting_mode: "simple" | "quadratic";
  pairwise_enabled: boolean;
  tracks: { id: string; name: string; slug: string; description: string; order: number }[];
  prizes: { id: string; name: string; value: string; track: string | null; order: number }[];
  rubric: {
    id: string;
    name: string;
    criteria: {
      id: string;
      name: string;
      description: string;
      weight: string;
      min: number;
      max: number;
      order: number;
    }[];
  } | null;
  state: string;
};

// Matches apps/events/serializers.py MembershipSerializer.
export type Membership = {
  id: string;
  user: string;
  user_email: string;
  user_name: string;
  role: "organizer" | "judge" | "participant" | "admin";
  created_at: string;
};

// Matches apps/judging/views.py BatchInviteView.
export type BulkInviteResponse = {
  invited: number;
};

// Matches apps/judging/assignment.py run_assignment's return dict.
export type AssignmentRunResponse = {
  batch_id: string;
  n_assignments: number;
  judges_with_zero_projects: string[];
  seed_used: number;
  attempts: number;
};

// Matches apps/normalization/views.py NormalizeView response.
export type NormalizeResponse = {
  run_id: string;
  raw_sigma: number;
  normalized_sigma: number;
  is_connected: boolean;
  iterations: number;
  n_projects: number;
  n_judges: number;
  n_reviews: number;
  proof: string;
};

// Matches apps/judging/views.py MyBatchView response — real names,
// unlike GET /api/judge/scores which returns bare project/criterion
// UUIDs.
export type BatchProject = {
  id: string;
  name: string;
  tagline: string;
  submitted: boolean;
  reviewed: boolean;
  submitted_at: string | null;
};

export type MyBatchResponse = {
  projects: BatchProject[];
  progress: { scored: number; total: number };
};

export type ScoreSavePayload = {
  scores: { criterion_id: string; value: number }[];
  comment?: string;
};

export type ScoreSaveResponse = {
  saved: boolean;
};

export type ScoreSubmitResponse = {
  submitted_at: string;
};

// Matches apps/certificates/views.py certificate_view response.
export type CertificateResponse = {
  public_id: string;
  submission_id: string;
  issued_at: string;
  signed_payload: Record<string, unknown>;
  signature: string;
  signature_algorithm: string;
};

// Matches apps/widget/views.py widget_gallery response.
export type WidgetGalleryItem = {
  id: string;
  name: string;
  tagline: string;
  track_slug: string;
};

export type WidgetGalleryResponse = {
  items: WidgetGalleryItem[];
  event: string;
};

// Matches apps/voting/views.py VoteResultsView.
export type VoteResultRow = {
  project_id: string;
  project_name: string;
  vote_count: number;
  total_votes: number;
};

export type VoteResultsResponse = {
  event_slug: string;
  voting_mode: "simple" | "quadratic";
  results_visible: boolean;
  results: VoteResultRow[];
};

// Matches apps/audit/views.py AuditLogView.
export type AuditLogEntry = {
  id: string;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  result: "success" | "denied" | "error";
  created_at: string;
};

export type AuditLogResponse = {
  event_slug: string;
  entries: AuditLogEntry[];
};

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}
