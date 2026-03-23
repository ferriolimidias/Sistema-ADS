export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded bg-gray-200 ${className}`} />;
}

export function CampaignSkeleton() {
  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-xl bg-white p-5 shadow-sm">
          <Skeleton className="mb-4 h-7 w-72" />
          <Skeleton className="h-4 w-96" />
          <Skeleton className="mt-4 h-10 w-48" />
        </div>

        {Array.from({ length: 2 }).map((_, idx) => (
          <div key={idx} className="rounded-xl bg-white p-5 shadow-sm">
            <Skeleton className="mb-4 h-6 w-56" />
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((__, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((__, i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
