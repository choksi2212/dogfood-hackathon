import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading pairwise ranking">
      <span className="sr-only">Loading ranking…</span>
      <Skeleton className="h-3 w-40" />
      <Skeleton className="mt-4 h-10 w-72 max-w-full" />
      <Skeleton className="mt-4 h-4 w-full max-w-2xl" />
      <div className="my-8 grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <div key={index} className="surface p-5">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="mt-4 h-8 w-16" />
            <Skeleton className="mt-4 h-3 w-40 max-w-full" />
          </div>
        ))}
      </div>
      <div className="surface overflow-hidden">
        <div className="border-b p-6">
          <Skeleton className="h-5 w-40" />
        </div>
        <div className="border-b bg-bg-overlay px-6 py-4">
          <Skeleton className="h-3 w-full" />
        </div>
        {[0, 1, 2, 3, 4, 5].map((index) => (
          <div
            key={index}
            className="flex items-center gap-8 border-b px-6 py-5 last:border-0"
          >
            <Skeleton className="h-5 w-10" />
            <div className="flex-1">
              <Skeleton className="h-4 w-48 max-w-full" />
              <Skeleton className="mt-2 h-2 w-20" />
            </div>
            <Skeleton className="hidden h-4 w-32 sm:block" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}
