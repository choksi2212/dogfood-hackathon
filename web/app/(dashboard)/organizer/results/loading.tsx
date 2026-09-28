import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div
      role="status"
      aria-label="Loading results and audit log"
      className="space-y-8"
    >
      <span className="sr-only">Loading results and audit log…</span>
      <div className="space-y-3">
        <Skeleton className="h-3 w-44 bg-bg-overlay" />
        <Skeleton className="h-10 w-64 bg-bg-overlay" />
        <Skeleton className="h-4 w-96 max-w-full bg-bg-overlay" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="surface rounded-xl p-5">
            <Skeleton className="h-4 w-28 bg-bg-overlay" />
            <Skeleton className="mt-5 h-8 w-16 bg-bg-overlay" />
          </div>
        ))}
      </div>
      {Array.from({ length: 2 }, (_, section) => (
        <section key={section} className="space-y-4">
          <Skeleton className="h-7 w-44 bg-bg-overlay" />
          <Skeleton className="h-4 w-72 max-w-full bg-bg-overlay" />
          <div className="surface overflow-hidden rounded-2xl">
            <div className="flex gap-10 border-b px-6 py-4">
              {Array.from({ length: 4 }, (_, column) => (
                <Skeleton key={column} className="h-3 w-20 bg-bg-overlay" />
              ))}
            </div>
            {Array.from({ length: 5 }, (_, row) => (
              <div
                key={row}
                className="flex items-center gap-6 border-b px-6 py-5 last:border-b-0"
              >
                <Skeleton className="h-4 w-20 shrink-0 bg-bg-overlay" />
                <Skeleton className="h-4 w-40 bg-bg-overlay" />
                <Skeleton className="ml-auto hidden h-4 w-28 bg-bg-overlay sm:block" />
                <Skeleton className="ml-auto h-6 w-20 rounded-full bg-bg-overlay" />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
