import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading project and rubric">
      <span className="sr-only">Loading project and rubric…</span>
      <Skeleton className="mb-8 h-4 w-36" />
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
        <div>
          <Skeleton className="h-3 w-40" />
          <Skeleton className="mt-6 h-12 w-3/4" />
          <Skeleton className="mt-5 h-5 w-full" />
          <Skeleton className="mt-3 h-5 w-2/3" />
          <div className="surface mt-8 p-6">
            <Skeleton className="mb-5 h-5 w-32" />
            {[0, 1, 2, 3].map((index) => (
              <Skeleton key={index} className="mt-3 h-3 w-full" />
            ))}
            <Skeleton className="mt-6 h-4 w-1/2" />
          </div>
          <div className="surface mt-6 p-6">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-5 h-12 w-full rounded-xl" />
            <Skeleton className="mt-3 h-12 w-full rounded-xl" />
          </div>
        </div>
        <div className="surface overflow-hidden">
          <div className="border-b p-7">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-4 h-6 w-52" />
          </div>
          <div className="space-y-5 p-7">
            {[0, 1, 2].map((index) => (
              <div key={index} className="rounded-xl border p-5">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="mt-4 h-3 w-full" />
                <Skeleton className="mt-7 h-6 w-full rounded-full" />
                <Skeleton className="mt-6 h-16 w-full rounded-lg" />
              </div>
            ))}
            <Skeleton className="h-11 w-full rounded-full" />
          </div>
        </div>
      </div>
    </div>
  );
}
