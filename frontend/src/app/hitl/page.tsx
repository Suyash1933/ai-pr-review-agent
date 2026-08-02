"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Empty } from "@/components/Empty";
import { VerdictChip } from "@/components/VerdictChip";
import type { HITLItem, Paginated } from "@/lib/types";

export default function HITLQueuePage() {
  const { data, error, isLoading, mutate } =
    useSWR<Paginated<HITLItem>>("/api/v1/hitl/queue?limit=100");
  const [deleting, setDeleting] = useState<string | null>(null);

  const items = data?.items ?? [];
  const pending = items
    .filter((h) => h.status === "pending" || h.status === "in_review")
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Delete this HITL item?")) return;
    setDeleting(id);
    try {
      await fetch(`/api/v1/hitl/${encodeURIComponent(id)}`, {
        method: "DELETE",
        credentials: "include",
      });
      await mutate();
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">HITL Queue</h1>
        <p className="text-muted text-sm mt-1">
          Items escalated by low confidence or critical findings.
          {pending.length > 0 && (
            <span className="text-warn ml-2">{pending.length} pending</span>
          )}
        </p>
      </div>

      {error ? (
        <Empty>Failed to load: {error.message}</Empty>
      ) : isLoading ? (
        <Empty>Loading…</Empty>
      ) : pending.length === 0 ? (
        <Empty>Queue is clear.</Empty>
      ) : (
        <div className="border border-border rounded-lg bg-panel divide-y divide-border">
          {pending.map((h, index) => (
            <div
              key={h.id}
              className="flex items-start justify-between px-4 py-3 hover:bg-bg gap-4"
            >
              <Link
                href={`/hitl/${encodeURIComponent(h.id)}`}
                className="min-w-0 flex-1"
              >
                <div className="font-mono text-sm truncate">
                  <span className="text-muted mr-2">#{pending.length - index}</span>
                  {h.repo_full_name} #{h.pr_number}
                </div>
                <div className="text-sm text-muted mt-0.5 truncate">
                  {h.escalation_reason}
                </div>
                <div className="text-xs text-muted font-mono mt-1">
                  conf {(h.overall_confidence * 100).toFixed(0)}% ·{" "}
                  {new Date(h.created_at).toLocaleString()}
                </div>
              </Link>
              <div className="flex items-center gap-2 shrink-0">
                <VerdictChip verdict={h.agent_verdict} />
                <button
                  onClick={(e) => handleDelete(e, h.id)}
                  disabled={deleting === h.id}
                  className="text-muted hover:text-err transition text-xs px-2 py-1
                             border border-border rounded hover:border-err/30
                             disabled:opacity-50"
                  title="Delete this item"
                >
                  {deleting === h.id ? "..." : "✕"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
