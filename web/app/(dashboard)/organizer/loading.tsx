import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div
      role="status"
      aria-label="Loading event dashboard"
      className="space-y-8"
    >
      <span className="sr-only">Loading event dashboard…</span>
      <div className="space-y-3">
        <Skeleton className="h-3 w-44 bg-bg-overlay" />
        <Skeleton className="h-10 w-72 max-w-full bg-bg-overlay" />
        <Skeleton className="h-4 w-96 max-w-full bg-bg-overlay" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="surface rounded-xl p-5">
            <Skeleton className="h-4 w-20 bg-bg-overlay" />
            <Skeleton className="mt-5 h-10 w-16 bg-bg-overlay" />
            <Skeleton className="mt-3 h-3 w-36 bg-bg-overlay" />
          </div>
        ))}
      </div>
      <div className="surface grid gap-6 rounded-2xl p-6 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index}>
            <Skeleton className="h-3 w-28 bg-bg-overlay" />
            <Skeleton className="mt-3 h-5 w-full bg-bg-overlay" />
          </div>
        ))}
      </div>
      <div className="space-y-4">
        <Skeleton className="h-7 w-48 bg-bg-overlay" />
        <div className="surface overflow-hidden rounded-2xl">
          <div className="border-b p-5">
            <Skeleton className="h-9 w-72 max-w-full bg-bg-overlay" />
          </div>
          {Array.from({ length: 5 }, (_, index) => (
            <div
              key={index}
              className="flex items-center gap-4 border-b p-4 last:border-b-0"
            >
              <Skeleton className="size-9 shrink-0 rounded-full bg-bg-overlay" />
              <Skeleton className="h-4 w-32 bg-bg-overlay" />
              <Skeleton className="ml-auto hidden h-4 w-44 bg-bg-overlay sm:block" />
              <Skeleton className="ml-auto h-6 w-20 rounded-full bg-bg-overlay" />
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="surface rounded-2xl p-6">
            <Skeleton className="size-11 rounded-xl bg-bg-overlay" />
            <Skeleton className="mt-5 h-6 w-40 bg-bg-overlay" />
            <Skeleton className="mt-3 h-12 w-full bg-bg-overlay" />
            <Skeleton className="mt-6 h-24 w-full bg-bg-overlay" />
            <Skeleton className="mt-5 h-10 w-full rounded-full bg-bg-overlay" />
          </div>
        ))}
      </div>
    </div>
  );
}
