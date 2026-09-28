import { Skeleton } from "@/components/ui/skeleton";

export function RouteLoading({ cards = false }: { cards?: boolean }) {
  return (
    <div role="status" aria-label="Loading content" className="space-y-6">
      <span className="sr-only">Loading content…</span>
      <Skeleton className="h-3 w-32" />
      <Skeleton className="h-10 w-64 max-w-full" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div
        className={
          cards ? "grid gap-6 sm:grid-cols-2 lg:grid-cols-3" : "space-y-4"
        }
      >
        {Array.from({ length: cards ? 6 : 4 }, (_, i) => (
          <div key={i} className="rounded-xl border bg-bg-elevated p-6">
            {cards && <Skeleton className="mb-6 h-28 w-full" />}
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="mt-3 h-3 w-full" />
            <Skeleton className="mt-3 h-3 w-1/3" />
          </div>
        ))}
      </div>
    </div>
  );
}
