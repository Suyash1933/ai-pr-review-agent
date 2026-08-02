"use client";

import useSWR from "swr";
import Link from "next/link";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import type { HITLItem, Paginated, ReviewSummary } from "@/lib/types";

const ACTIVE_STATUSES = new Set([
  "queued",
  "in_progress",
  "agents_running",
  "aggregating",
  "posting",
]);

export default function DashboardPage() {
  const { data: reviewsResp, error: reviewsErr } =
    useSWR<Paginated<ReviewSummary>>("/api/v1/reviews?limit=50");
  const { data: hitlResp, error: hitlErr } =
    useSWR<Paginated<HITLItem>>("/api/v1/hitl/queue?limit=50");

  const reviews = reviewsResp?.items ?? [];
  const hitl = hitlResp?.items ?? [];
  const recent = reviews.slice(0, 8);
  const pendingHitl = hitl.filter((h) => h.status === "pending" || h.status === "in_review");
  const escalated = reviews.filter((r) => r.status === "escalated" || r.needs_human_review).length;
  const activeReviews = reviews.filter((r) => ACTIVE_STATUSES.has(r.status));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted text-sm mt-1">
          Live state of the review pipeline. Polls every 5s.
        </p>
      </div>

      {/* Active review banner */}
      {activeReviews.length > 0 && (
        <div className="border border-accent/30 bg-accent/10 rounded-lg px-4 py-4 flex items-start gap-4 animate-pulse">
          <div className="mt-0.5">
            <Spinner />
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium text-accent">
              AI Agents are reviewing {activeReviews.length} PR{activeReviews.length > 1 ? "s" : ""}...
            </div>
            <div className="text-xs text-muted mt-1 space-y-1">
              {activeReviews.map((r) => (
                <div key={r.id} className="flex items-center gap-2">
                  <span className="font-mono">{r.repo_full_name} #{r.pr_number}</span>
                  <ReviewStatusBadge status={r.status} />
                </div>
              ))}
            </div>
            <div className="text-xs text-muted/60 mt-2">
              4 agents (Security · Quality · Tests · Docs) running in parallel.
              Results will appear in Reviews or HITL Queue.
            </div>
          </div>
        </div>
      )}

      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat label="Total Reviews" value={reviewsResp?.total} err={!!reviewsErr} />
        <Stat label="In Progress" value={activeReviews.length} err={!!reviewsErr}
              tone={activeReviews.length > 0 ? "accent" : "ok"} />
        <Stat
          label="HITL Pending"
          value={pendingHitl.length}
          err={!!hitlErr}
          tone={pendingHitl.length > 0 ? "warn" : "ok"}
        />
        <Stat label="Needs Human" value={escalated} err={!!reviewsErr} />
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-medium">Recent Reviews</h2>
          <Link href="/reviews" className="text-sm text-accent">
            View all →
          </Link>
        </div>
        {reviewsErr ? (
          <Empty>Could not load reviews: {String(reviewsErr.message)}</Empty>
        ) : recent.length === 0 ? (
          <Empty>No reviews yet. Open a PR on a watched repo.</Empty>
        ) : (
          <div className="border border-border rounded-lg bg-panel divide-y divide-border">
            {recent.map((r) => {
              const isActive = ACTIVE_STATUSES.has(r.status);
              return (
                <Link
                  key={r.id}
                  href={`/reviews/${encodeURIComponent(r.id)}`}
                  className={`flex items-center justify-between px-4 py-3 hover:bg-bg gap-3 ${
                    isActive ? "bg-accent/5" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <div className="font-mono text-sm truncate flex items-center gap-2">
                      {isActive && <Spinner size="sm" />}
                      {r.repo_full_name} #{r.pr_number}
                    </div>
                    <div className="text-xs text-muted truncate mt-0.5">
                      {r.pr_title}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {isActive ? (
                      <span className="text-xs text-accent">Reviewing...</span>
                    ) : (
                      <VerdictChip verdict={r.verdict} />
                    )}
                    <ReviewStatusBadge status={r.status} />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-medium">HITL Queue</h2>
          <Link href="/hitl" className="text-sm text-accent">
            Open queue →
          </Link>
        </div>
        {pendingHitl.length === 0 ? (
          <Empty>Queue is clear.</Empty>
        ) : (
          <div className="border border-border rounded-lg bg-panel divide-y divide-border">
            {pendingHitl.slice(0, 5).map((h) => (
              <Link
                key={h.id}
                href={`/hitl/${encodeURIComponent(h.id)}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-bg gap-3"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm truncate">
                    {h.repo_full_name} #{h.pr_number}
                  </div>
                  <div className="text-xs text-muted truncate">
                    {h.escalation_reason}
                  </div>
                </div>
                <VerdictChip verdict={h.agent_verdict} />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  err,
  tone,
}: {
  label: string;
  value?: number;
  err?: boolean;
  tone?: "ok" | "warn" | "err" | "accent";
}) {
  const color =
    tone === "warn"
      ? "text-warn"
      : tone === "err"
      ? "text-err"
      : tone === "ok"
      ? "text-ok"
      : tone === "accent"
      ? "text-accent"
      : "text-white";
  return (
    <div className="border border-border rounded-lg bg-panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`text-2xl font-mono mt-1 ${color}`}>
        {err ? "—" : value ?? "…"}
      </div>
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
