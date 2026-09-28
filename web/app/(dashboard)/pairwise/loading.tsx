import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading pairwise comparison">
      <span className="sr-only">Loading comparisons…</span>
      <Skeleton className="h-3 w-36" />
      <Skeleton className="mt-4 h-10 w-72 max-w-full" />
      <Skeleton className="mt-4 h-4 w-full max-w-xl" />
      <Skeleton className="my-8 h-14 w-full rounded-xl" />
      <div className="grid gap-6 md:grid-cols-2">
        {[0, 1].map((index) => (
          <div key={index} className="surface p-8">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="mt-8 h-36 w-full rounded-xl" />
            <Skeleton className="mt-7 h-8 w-3/4" />
            <Skeleton className="mt-4 h-4 w-full" />
            <Skeleton className="mt-3 h-4 w-2/3" />
            <Skeleton className="mt-8 h-12 w-full rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
