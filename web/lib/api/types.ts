export type Submission = {
  id: string;
  name: string;
  tagline: string;
  description: string;
  track_slug: string;
  thumbnail_path: string | null;
  submitted_at: string | null;
};

export type GalleryResponse = {
  total: number;
  page: number;
  page_size: number;
  items: Submission[];
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
