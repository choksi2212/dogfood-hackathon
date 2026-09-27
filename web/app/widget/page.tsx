"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";
import { PageHeader } from "@/components/PageHeader";
import styles from "./widget.module.css";

export default function WidgetPage() {
  const targetRef = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [snippet, setSnippet] = useState("");

  useEffect(() => {
    const scriptUrl = api.widgetScriptUrl();
    setSnippet(
      [
        '<div id="dogfood-widget"></div>',
        "<script>",
        "  window.DOGFOOD_WIDGET = {",
        `    event: "${EVENT_SLUG}",`,
        '    target: document.getElementById("dogfood-widget"),',
        "  };",
        "</" + "script>",
        `<script src="${scriptUrl}"></` + "script>",
      ].join("\n"),
    );

    // Mirrors what a third-party embedder's page does: set the config
    // global, then load the real widget.js script — the same file this
    // page's own embed snippet points at, fetched cross-origin exactly
    // as an external site would (widget.js ships Access-Control-Allow-
    // Origin: * for this reason).
    if (!targetRef.current) return;
    (window as unknown as { DOGFOOD_WIDGET?: object }).DOGFOOD_WIDGET = {
      event: EVENT_SLUG,
      target: targetRef.current,
    };
    const script = document.createElement("script");
    script.src = scriptUrl;
    script.onload = () => setLoaded(true);
    document.body.appendChild(script);
    return () => {
      document.body.removeChild(script);
    };
  }, []);

  return (
    <div>
      <PageHeader
        title="Embeddable widget"
        description={
          <>
            Drop this on any page to show the live gallery — no auth, no
            iframe, just a script tag and the public{" "}
            <code>/api/widget/gallery</code> feed.
          </>
        }
      />

      <h2 className={styles.sectionTitle}>Embed snippet</h2>
      <pre className={styles.snippet}>{snippet}</pre>

      <h2 className={styles.sectionTitle}>Live preview</h2>
      <p className={styles.hint}>
        This is the real widget.js running on this page, fetching the real
        feed cross-origin — not a mock.
      </p>
      <div className={styles.previewFrame}>
        {!loaded && <p className={styles.hint}>Loading widget...</p>}
        <div ref={targetRef} />
      </div>
    </div>
  );
}
