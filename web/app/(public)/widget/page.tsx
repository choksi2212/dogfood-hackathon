"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { EVENT_SLUG } from "@/lib/api/routes";

export default function WidgetPage() {
  const targetRef = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const scriptUrl = api.widgetScriptUrl();
  const snippet = [
    '<div id="dogfood-widget"></div>',
    "<script>",
    "  window.DOGFOOD_WIDGET = {",
    `    event: "${EVENT_SLUG}",`,
    '    target: document.getElementById("dogfood-widget"),',
    "  };",
    "</" + "script>",
    `<script src="${scriptUrl}"></` + "script>",
  ].join("\n");

  useEffect(() => {
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
  }, [scriptUrl]);

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Embeddable widget</h1>
      <p className="mt-1 max-w-lg text-muted-foreground">
        Drop this on any page to show the live gallery — no auth, no iframe, just a
        script tag and the public <code>/api/widget/gallery</code> feed.
      </p>

      <h2 className="mt-8 mb-3 text-lg font-semibold">Embed snippet</h2>
      <pre className="max-w-xl overflow-x-auto whitespace-pre rounded-lg border bg-muted p-3 text-sm">
        {snippet}
      </pre>

      <h2 className="mt-8 mb-3 text-lg font-semibold">Live preview</h2>
      <p className="text-sm text-muted-foreground">
        This is the real widget.js running on this page, fetching the real feed
        cross-origin — not a mock.
      </p>
      <div className="mt-3 max-w-xl rounded-lg border border-dashed p-4">
        {!loaded && <p className="text-sm text-muted-foreground">Loading widget…</p>}
        <div ref={targetRef} />
      </div>
    </div>
  );
}
