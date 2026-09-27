"use client";

import styles from "./ranking.module.css";

type ExportRow = {
  rank: number;
  project_name: string;
  project_id: string;
  theta: number;
  wins: number;
  losses: number;
  ties: number;
};

function toCsv(rows: ExportRow[]): string {
  const header = ["rank", "project_name", "project_id", "theta", "wins", "losses", "ties"];
  const escape = (v: string | number) => {
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    header.join(","),
    ...rows.map((r) =>
      [r.rank, r.project_name, r.project_id, r.theta, r.wins, r.losses, r.ties]
        .map(escape)
        .join(","),
    ),
  ];
  return lines.join("\n");
}

export function ExportCsvButton({
  rows,
  eventSlug,
}: {
  rows: ExportRow[];
  eventSlug: string;
}) {
  function handleClick() {
    const csv = toCsv(rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pairwise-ranking-${eventSlug}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <button className={styles.exportButton} onClick={handleClick}>
      Export CSV
    </button>
  );
}
