"use client";

import useSWR from "swr";
import Link from "next/link";
import type { Paginated, ReviewSummary } from "@/lib/types";

const ACTIVE_STATUSES = new Set([
  "queued",
  "in_progress",
  "agents_running",
  "aggregating",
  "posting",
]);

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  in_progress: "Starting",
  agents_running: "Agents analyzing",
  aggregating: "Merging results",
  posting: "Posting to GitHub",
};

export function ReviewBanner() {
  const { data } = useSWR<Paginated<ReviewSummary>>("/api/v1/reviews?limit=20", {
    refreshInterval: 3000,
  });

  const active = (data?.items ?? []).filter((r) => ACTIVE_STATUSES.has(r.status));

  if (active.length === 0) return null;

  return (
    <div className="fixed top-0 right-0 z-50 m-4 ml-60">
      <div className="bg-panel border border-accent/40 rounded-lg shadow-lg shadow-accent/10 px-4 py-3 max-w-sm">
        <div className="flex items-center gap-2 mb-2">
          <Spinner />
          <span className="text-sm font-medium text-accent">
            Reviewing {active.length} PR{active.length > 1 ? "s" : ""}
          </span>
        </div>
        <div className="space-y-1.5">
          {active.map((r) => (
            <Link
              key={r.id}
              href={`/reviews/${encodeURIComponent(r.id)}`}
              className="block hover:bg-bg rounded px-2 py-1 -mx-2 transition"
            >
              <div className="font-mono text-xs text-white truncate">
                {r.repo_full_name} #{r.pr_number}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                <span className="text-[10px] text-muted">
                  {STAGE_LABELS[r.status] || r.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
        <div className="text-[10px] text-muted/50 mt-2 border-t border-border pt-1.5">
          Security · Quality · Tests · Docs — running in parallel
        </div>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="w-4 h-4 animate-spin text-accent"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
