// The five route names run.py (and .dogfood.toml's [routes] block) know
// about: gallery, submit, judge_scores, peer_scores, csv_export. Every
// call the frontend makes to the backend goes through one of these, so a
// path change on either side is a one-line fix here — not a hunt through
// components.
export const EVENT_SLUG = "sample-hack-2026";

export const routes = {
  gallery: () => "/api/gallery",
  submit: (slug: string = EVENT_SLUG) => `/api/events/${slug}/submit`,
  judgeScores: () => "/api/judge/scores",
  peerScores: (judge: string) => `/api/judge/peer-scores?judge=${judge}`,
  csvExport: () => "/api/csv_export",
  // Not part of the five acceptance routes, but real documented
  // endpoints (apps/accounts, apps/voting, apps/pairwise) — needed to
  // get the session cookie the other routes require, and to cover T3/T4
  // surfaces run.py never touches.
  login: () => "/api/login",
  vote: (id: string, slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/submissions/${id}/vote`,
  pairwiseBallots: (slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/pairwise/ballots`,
  pairwiseRanking: (slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/pairwise/ranking`,
  // Organizer dashboard (apps/events, apps/judging, apps/normalization).
  eventDetail: (slug: string = EVENT_SLUG) => `/api/events/${slug}/`,
  memberships: (slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/memberships`,
  bulkInviteJudges: (slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/judges/bulk-invite`,
  assignmentsRun: (slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/assignments/run`,
  normalize: (slug: string = EVENT_SLUG) => `/api/events/${slug}/normalize`,
  // Judge console (apps/judging) — real names, not the raw
  // project_id/criterion_id pairs from GET /api/judge/scores.
  meBatch: (slug: string = EVENT_SLUG) => `/api/events/${slug}/me/batch`,
  scoreSave: (projectId: string, slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/me/batch/${projectId}/scores`,
  scoreSubmit: (projectId: string, slug: string = EVENT_SLUG) =>
    `/api/events/${slug}/me/batch/${projectId}/submit`,
  // apps/certificates — public, no auth (a certificate is a public,
  // signed record; anyone with the public_id can verify it).
  certificate: (publicId: string) => `/api/certificates/${publicId}`,
  // apps/widget — widget.js is mounted at the project root, not under
  // /api/, and ships its own Access-Control-Allow-Origin: * (it's meant
  // to be <script>-embedded on third-party sites), so callers use
  // NEXT_PUBLIC_WIDGET_BASE directly rather than the /api/* proxy.
  widgetGallery: (slug: string = EVENT_SLUG) =>
    `/api/widget/gallery?event=${slug}`,
} as const;
