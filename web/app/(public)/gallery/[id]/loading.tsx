import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading project" className="space-y-7">
      <span className="sr-only">Loading project…</span>
      <Skeleton className="h-4 w-32" />
      <div className="rounded-3xl border border-border bg-bg-elevated p-9 sm:p-12">
        <Skeleton className="h-5 w-44" />
        <Skeleton className="mt-8 h-14 w-3/4" />
        <Skeleton className="mt-5 h-5 w-2/3" />
        <Skeleton className="mt-8 h-4 w-1/2" />
      </div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="rounded-2xl border border-border bg-bg-elevated p-8">
          <Skeleton className="h-6 w-40" />
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="mt-5 h-4 w-full" />
          ))}
        </div>
        <div className="rounded-2xl border border-border bg-bg-elevated p-6">
          <Skeleton className="h-5 w-40" />
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="mt-5 h-16 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
