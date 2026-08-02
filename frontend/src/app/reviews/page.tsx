"use client";

import useSWR from "swr";
import Link from "next/link";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import type { Paginated, ReviewSummary } from "@/lib/types";

const ACTIVE_STATUSES = new Set([
  "queued",
  "in_progress",
  "agents_running",
  "aggregating",
  "posting",
]);

export default function ReviewsPage() {
  const { data, error, isLoading } =
    useSWR<Paginated<ReviewSummary>>("/api/v1/reviews?limit=100");

  const items = data?.items ?? [];
  const activeReviews = items.filter((r) => ACTIVE_STATUSES.has(r.status));
  const hasActive = activeReviews.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Reviews</h1>
        <p className="text-muted text-sm mt-1">
          All PR reviews handled by the agent. {data ? `(${data.total} total)` : ""}
        </p>
      </div>

      {/* Active review banner */}
      {hasActive && (
        <div className="border border-accent/30 bg-accent/10 rounded-lg px-4 py-3 flex items-center gap-3">
          <Spinner />
          <div>
            <div className="text-sm font-medium text-accent">
              {activeReviews.length} review{activeReviews.length > 1 ? "s" : ""} in progress
            </div>
            <div className="text-xs text-muted mt-0.5">
              {activeReviews.map((r) => `${r.repo_full_name} #${r.pr_number}`).join(", ")}
            </div>
          </div>
        </div>
      )}

      {error ? (
        <Empty>Failed to load: {error.message}</Empty>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-12 gap-3">
          <Spinner />
          <span className="text-muted text-sm">Loading reviews...</span>
        </div>
      ) : items.length === 0 ? (
        <Empty>No reviews yet. Activate a repo and open a PR to get started.</Empty>
      ) : (
        <div className="border border-border rounded-lg bg-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-bg text-muted text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Repo / PR</th>
                <th className="text-left px-4 py-2">Commit</th>
                <th className="text-left px-4 py-2">Findings</th>
                <th className="text-left px-4 py-2">Verdict</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((r) => {
                const isActive = ACTIVE_STATUSES.has(r.status);
                return (
                  <tr
                    key={r.id}
                    className={`hover:bg-bg ${isActive ? "bg-accent/5" : ""}`}
                  >
                    <td className="px-4 py-3 font-mono">
                      <Link
                        href={`/reviews/${encodeURIComponent(r.id)}`}
                        className="text-accent"
                      >
                        {r.repo_full_name} #{r.pr_number}
                      </Link>
                      <div className="text-xs text-muted truncate max-w-xs">
                        {r.pr_title}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-muted">
                      {r.head_commit_sha?.slice(0, 7)}
                    </td>
                    <td className="px-4 py-3">{r.finding_count ?? "—"}</td>
                    <td className="px-4 py-3">
                      {isActive ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-accent">
                          <Spinner size="sm" /> Reviewing...
                        </span>
                      ) : (
                        <VerdictChip verdict={r.verdict} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ReviewStatusBadge status={r.status} />
                    </td>
                    <td className="px-4 py-3 text-muted text-xs">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Spinner({ size = "md" }: { size?: "sm" | "md" }) {
  const dim = size === "sm" ? "w-3.5 h-3.5" : "w-5 h-5";
  return (
    <svg
      className={`${dim} animate-spin text-accent`}
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
