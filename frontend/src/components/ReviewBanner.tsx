"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";

interface ActiveReview {
  workflow_id: string;
  repo_full_name: string;
  pr_number: number;
  status: string;
}

interface CompletedNotif {
  id: string;
  repo: string;
  pr: number;
  timestamp: number;
}

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  in_progress: "Starting agents",
  agents_running: "Agents analyzing code",
  aggregating: "Merging results",
  posting: "Posting to GitHub",
};

export function ReviewBanner() {
  const { data: active } = useSWR<ActiveReview[]>("/api/v1/queue/active", {
    refreshInterval: 2000,
    revalidateOnFocus: true,
  });
  const [completed, setCompleted] = useState<CompletedNotif[]>([]);
  const [prevIds, setPrevIds] = useState<Set<string>>(new Set());

  const reviews = active ?? [];
  const currentIds = new Set(reviews.map((r) => r.workflow_id));

  // Detect when review finishes (was active, now gone)
  useEffect(() => {
    if (prevIds.size > 0) {
      for (const id of prevIds) {
        if (!currentIds.has(id)) {
          const parts = id.split(":");
          setCompleted((prev) => [
            {
              id,
              repo: parts[0] || "unknown",
              pr: parseInt(parts[1]) || 0,
              timestamp: Date.now(),
            },
            ...prev,
          ]);
        }
      }
    }
    setPrevIds(currentIds);
  }, [JSON.stringify([...currentIds])]);

  // Auto-dismiss completed after 8 seconds
  useEffect(() => {
    if (completed.length === 0) return;
    const timer = setInterval(() => {
      setCompleted((prev) => prev.filter((c) => Date.now() - c.timestamp < 8000));
    }, 1000);
    return () => clearInterval(timer);
  }, [completed.length]);

  if (reviews.length === 0 && completed.length === 0) return null;

  return (
    <div className="fixed top-3 right-3 z-50 space-y-2" style={{ maxWidth: "320px" }}>
      {/* Active reviews */}
      {reviews.length > 0 && (
        <div className="bg-panel border border-accent/40 rounded-lg shadow-lg shadow-accent/10 px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <Spinner />
            <span className="text-sm font-medium text-accent">
              Reviewing {reviews.length} PR{reviews.length > 1 ? "s" : ""}
            </span>
          </div>
          <div className="space-y-2">
            {reviews.map((r) => (
              <div key={r.workflow_id} className="px-1">
                <div className="font-mono text-xs text-white truncate">
                  {r.repo_full_name} #{r.pr_number}
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  <span className="text-[10px] text-muted">
                    {STAGE_LABELS[r.status] || r.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <div className="text-[10px] text-muted/50 mt-2 border-t border-border pt-1.5">
            Security · Quality · Tests · Docs
          </div>
        </div>
      )}

      {/* Completed notifications */}
      {completed.map((c) => (
        <Link
          key={c.id}
          href="/reviews"
          className="block bg-panel border border-ok/40 rounded-lg shadow-lg px-4 py-3 hover:bg-bg transition"
        >
          <div className="flex items-center gap-2">
            <span className="text-ok text-sm">✓</span>
            <span className="text-sm font-medium text-ok">Review Complete</span>
          </div>
          <div className="font-mono text-xs text-white mt-1 truncate">
            {c.repo} #{c.pr}
          </div>
          <div className="text-[10px] text-muted mt-0.5">
            Click to view results
          </div>
        </Link>
      ))}
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
