import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div
      className="mx-auto max-w-3xl rounded-3xl border border-border bg-bg-elevated p-7 sm:p-10"
      role="status"
      aria-label="Verifying certificate"
    >
      <span className="sr-only">Verifying certificate…</span>
      <Skeleton className="size-16 rounded-2xl" />
      <Skeleton className="mt-7 h-3 w-44" />
      <Skeleton className="mt-5 h-10 w-2/3" />
      <Skeleton className="mt-6 h-8 w-40 rounded-full" />
      <Skeleton className="mt-5 h-4 w-full" />
      <div className="mt-8 rounded-2xl border border-border p-6">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex gap-6 py-4">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-4 flex-1" />
          </div>
        ))}
      </div>
      <Skeleton className="mt-8 h-12 w-full" />
    </div>
  );
}
