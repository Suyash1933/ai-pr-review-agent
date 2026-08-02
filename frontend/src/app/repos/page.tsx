"use client";

import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/lib/auth";
import { Empty } from "@/components/Empty";

interface GithubRepo {
  full_name: string;
  private: boolean;
  description: string | null;
  default_branch: string;
  is_active: boolean;
}

export default function ReposPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [toggling, setToggling] = useState<string | null>(null);

  const { data: repos, error, mutate } = useSWR<GithubRepo[]>(
    "/api/v1/auth/repos",
    async (url: string) => {
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch repos");
      return res.json();
    }
  );

  const toggleRepo = async (repo: GithubRepo) => {
    const action = repo.is_active ? "deactivate" : "activate";
    const encodedName = encodeURIComponent(repo.full_name.split("/")[0]) +
      "/" + encodeURIComponent(repo.full_name.split("/")[1]);

    setToggling(repo.full_name);
    try {
      const res = await fetch(`/api/v1/auth/repos/${encodedName}/${action}`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.detail || `Failed to ${action} repo`);
        return;
      }
      await mutate();
    } finally {
      setToggling(null);
    }
  };

  const filtered = (repos ?? []).filter((r) =>
    r.full_name.toLowerCase().includes(search.toLowerCase())
  );

  const activeCount = (repos ?? []).filter((r) => r.is_active).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">My Repositories</h1>
        <p className="text-muted text-sm mt-1">
          Toggle repos to enable automated PR review.
          {activeCount > 0 && (
            <span className="text-ok ml-2">{activeCount} active</span>
          )}
        </p>
      </div>

      <input
        type="text"
        placeholder="Search repos..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full bg-panel border border-border rounded-lg px-4 py-2
                   text-sm text-white placeholder-muted focus:outline-none
                   focus:border-accent"
      />

      {error ? (
        <Empty>Failed to load repos. Please try again.</Empty>
      ) : !repos ? (
        <Empty>Loading your GitHub repos...</Empty>
      ) : filtered.length === 0 ? (
        <Empty>No repos found.</Empty>
      ) : (
        <div className="border border-border rounded-lg bg-panel divide-y divide-border">
          {filtered.map((repo) => (
            <div
              key={repo.full_name}
              className="flex items-center justify-between px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-white truncate">
                    {repo.full_name}
                  </span>
                  {repo.private && (
                    <span className="text-xs bg-border px-1.5 py-0.5 rounded text-muted">
                      private
                    </span>
                  )}
                </div>
                {repo.description && (
                  <p className="text-xs text-muted mt-0.5 truncate">
                    {repo.description}
                  </p>
                )}
              </div>

              <button
                onClick={() => toggleRepo(repo)}
                disabled={toggling === repo.full_name}
                className={`ml-4 shrink-0 px-3 py-1.5 text-xs font-medium rounded-md transition
                  ${
                    repo.is_active
                      ? "bg-ok/20 text-ok border border-ok/30 hover:bg-err/20 hover:text-err hover:border-err/30"
                      : "bg-border text-muted hover:bg-accent/20 hover:text-accent hover:border-accent/30 border border-border"
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {toggling === repo.full_name
                  ? "..."
                  : repo.is_active
                  ? "Active"
                  : "Activate"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
