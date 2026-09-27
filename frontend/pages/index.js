/* DOGFOOD Portal — placeholder landing page.
 *
 * Mihir replaces this with the real screens. Until then this page
 * demonstrates the one-command bring-up: it fetches /api/gallery
 * through nginx and renders the project list, proving the frontend
 * can talk to the backend without any extra config.
 */

import { useEffect, useState } from "react";

export default function Home() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/gallery?event=sample-hack-2026")
      .then(async (resp) => {
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        return resp.json();
      })
      .then((body) => {
        if (cancelled) return;
        setItems(body.items || []);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(String(err));
        setStatus("error");
      });
    return () => { cancelled = true; };
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <h1 style={{ fontSize: 32, margin: 0 }}>DOGFOOD Portal</h1>
      <p style={{ color: "#555" }}>
        One-command bring-up. Backend (Django) + Frontend (Next.js) +
        observability stack (Prometheus / Grafana / Alertmanager) all
        running in docker compose.
      </p>

      <h2>Gallery</h2>
      {status === "loading" && <p>Loading…</p>}
      {status === "error" && (
        <p style={{ color: "#c00" }}>Backend unreachable: {error}</p>
      )}
      {status === "ready" && (
        <ul>
          {items.length === 0 && (
            <li style={{ color: "#888" }}>
              No submissions yet. Seed with{" "}
              <code>docker compose exec web python manage.py seed_fixtures</code>.
            </li>
          )}
          {items.map((item) => (
            <li key={item.id}>
              <strong>{item.name}</strong>
              {item.tagline ? <> — <em>{item.tagline}</em></> : null}
            </li>
          ))}
        </ul>
      )}

      <h2>Operator links</h2>
      <ul>
        <li><a href="/grafana/">Grafana dashboards</a> (admin / admin by default)</li>
        <li><a href="/prometheus/">Prometheus query UI</a></li>
        <li><a href="/alertmanager/">Alertmanager</a></li>
        <li><a href="/admin/">Django admin</a></li>
        <li><a href="/api/schema/">OpenAPI 3 schema (JSON)</a></li>
      </ul>

      <p style={{ marginTop: 40, color: "#888", fontSize: 13 }}>
        Mihir: replace <code>frontend/pages/index.js</code> and add the
        real screens. The nginx proxy already routes <code>/api/*</code>
        to the backend and <code>/</code> to this app — no rewiring
        needed.
      </p>
    </main>
  );
}
