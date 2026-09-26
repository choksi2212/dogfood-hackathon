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
} as const;
