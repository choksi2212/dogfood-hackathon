import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading your judging batch">
      <span className="sr-only">Loading your batch…</span>
      <Skeleton className="h-3 w-36" />
      <Skeleton className="mt-4 h-10 w-64" />
      <Skeleton className="mt-4 h-4 w-full max-w-xl" />
      <div className="surface my-8 flex items-center gap-6 p-8">
        <Skeleton className="size-28 shrink-0 rounded-full" />
        <div className="flex-1">
          <Skeleton className="h-6 w-64 max-w-full" />
          <Skeleton className="mt-4 h-4 w-48 max-w-full" />
        </div>
      </div>
      <div className="mb-5 flex justify-between gap-4">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-8 w-48 rounded-full" />
      </div>
      <div className="space-y-3">
        {[0, 1, 2, 3].map((index) => (
          <div key={index} className="surface flex items-center gap-5 p-6">
            <Skeleton className="size-11 shrink-0 rounded-xl" />
            <div className="flex-1">
              <Skeleton className="h-5 w-52 max-w-full" />
              <Skeleton className="mt-3 h-3 w-80 max-w-full" />
            </div>
            <Skeleton className="hidden h-9 w-32 rounded-full sm:block" />
          </div>
        ))}
      </div>
    </div>
  );
}
