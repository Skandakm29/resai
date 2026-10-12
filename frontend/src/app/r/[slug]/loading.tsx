import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="mx-auto h-14 w-14 rounded-2xl" />
      <Skeleton className="mx-auto h-8 w-64" />
      <Skeleton className="mx-auto h-4 w-80" />
      <div className="flex flex-wrap justify-center gap-2 pt-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-48 rounded-full" />
        ))}
      </div>
    </div>
  );
}
