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

export type JudgeScore = {
  submission_id: string;
  submission_name: string;
  criterion: string;
  score: number;
  max_score: number;
  comment: string | null;
};

export type JudgeScoresResponse = {
  judge: string;
  scores: JudgeScore[];
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
  };
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
