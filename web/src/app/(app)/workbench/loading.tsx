import { Skeleton } from "@/components/ui/states";

export default function Loading() {
  return (
    <div role="status" aria-live="polite" className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <span className="sr-only">Loading</span>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-8 w-72" />
      <Skeleton className="mt-3 h-4 w-[28rem] max-w-full" />
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    </div>
  );
}
