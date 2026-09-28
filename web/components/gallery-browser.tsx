"use client";

import { useEffect, useRef, useState } from "react";
import { Search, ArrowRight, LayoutGrid } from "lucide-react";
import { api } from "@/lib/api/client";
import type { GalleryResponse } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/portal-ui";
import { RouteError } from "@/components/route-error";
import { RouteLoading } from "@/components/route-loading";
import { ProjectCard } from "@/components/project-card";

export function GalleryBrowser({ preview = false }: { preview?: boolean }) {
  const [data, setData] = useState<GalleryResponse | null>(null);
  const [error, setError] = useState(false);
  const [track, setTrack] = useState("all");
  const [tracks, setTracks] = useState<string[]>([]);
  const [sort, setSort] = useState<"alpha" | "newest">("alpha");
  const [search, setSearch] = useState("");
  const [retry, setRetry] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const generation = useRef(0);

  useEffect(() => {
    let active = true;
    generation.current += 1;
    api
      .galleryPage({ track: track === "all" ? undefined : track, sort })
      .then((result) => {
        if (!active) return;
        setData(result);
        setTracks((prev) =>
          Array.from(
            new Set([...prev, ...result.items.map((item) => item.track_slug)]),
          ).sort(),
        );
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [track, sort, retry]);

  function resetQuery() {
    generation.current += 1;
    setData(null);
    setError(false);
    setMoreError(false);
    setLoadingMore(false);
  }
  async function loadMore() {
    if (!data?.next || loadingMore) return;
    const currentGeneration = generation.current;
    setLoadingMore(true);
    setMoreError(false);
    try {
      const result = await api.galleryPage({
        track: track === "all" ? undefined : track,
        sort,
        after: data.next,
      });
      if (currentGeneration !== generation.current) return;
      setData((prev) =>
        prev
          ? {
              ...result,
              items: Array.from(
                new Map(
                  [...prev.items, ...result.items].map((item) => [
                    item.id,
                    item,
                  ]),
                ).values(),
              ),
            }
          : result,
      );
      setTracks((prev) =>
        Array.from(
          new Set([...prev, ...result.items.map((item) => item.track_slug)]),
        ).sort(),
      );
    } catch {
      if (currentGeneration === generation.current) setMoreError(true);
    } finally {
      if (currentGeneration === generation.current) setLoadingMore(false);
    }
  }
  const items =
    data?.items.filter((item) =>
      `${item.name} ${item.tagline}`
        .toLowerCase()
        .includes(search.toLowerCase()),
    ) ?? [];

  return (
    <div>
      {!preview && (
        <div className="mb-7 flex flex-wrap items-end gap-4 rounded-xl border bg-bg-elevated p-4">
          <div className="min-w-48 flex-1 space-y-2">
            <Label
              htmlFor="gallery-search"
              className="text-xs text-text-secondary"
            >
              Search loaded projects
            </Label>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="absolute top-3.5 left-3 size-4 text-text-muted"
              />
              <Input
                id="gallery-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Find your next favorite idea…"
                className="pl-10"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="track-filter"
              className="text-xs text-text-secondary"
            >
              Track
            </Label>
            <Select
              value={track}
              onValueChange={(value) => {
                if (value !== null && value !== track) {
                  resetQuery();
                  setTrack(value);
                }
              }}
            >
              <SelectTrigger id="track-filter" className="min-w-36">
                <SelectValue>
                  {track === "all" ? "All tracks" : track}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All tracks</SelectItem>
                {tracks.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="gallery-sort"
              className="text-xs text-text-secondary"
            >
              Sort by
            </Label>
            <Select
              value={sort}
              onValueChange={(value) => {
                if (value !== null && value !== sort) {
                  resetQuery();
                  setSort(value as "alpha" | "newest");
                }
              }}
            >
              <SelectTrigger id="gallery-sort" className="min-w-36">
                <SelectValue>
                  {sort === "alpha" ? "Alphabetical" : "Newest first"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="alpha">Alphabetical</SelectItem>
                <SelectItem value="newest">Newest first</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      )}
      {error ? (
        <RouteError
          message="Could not load the gallery"
          reset={() => {
            resetQuery();
            setRetry((value) => value + 1);
          }}
        />
      ) : !data ? (
        <RouteLoading cards />
      ) : items.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title={
            search || track !== "all"
              ? "No matching projects loaded"
              : "The next big idea is on its way"
          }
          description={
            search || track !== "all"
              ? "Try another search, select a different track, or load more projects below."
              : "Submitted projects will appear here as soon as builders ship."
          }
        />
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {(preview ? items.slice(0, 6) : items).map((item, index) => (
            <ProjectCard key={item.id} item={item} index={index} />
          ))}
        </div>
      )}
      {!preview && data && !error && (
        <div className="mt-8 flex flex-col items-center gap-4">
          <p className="font-mono text-xs text-text-muted">
            {items.length} projects shown
            {data.next ? " · more to discover" : " · you’re all caught up"}
          </p>
          {moreError && (
            <RouteError
              message="Could not load more projects"
              reset={loadMore}
            />
          )}
          {data.next && (
            <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading projects…" : "Load more projects"}
              <ArrowRight className="size-4" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
