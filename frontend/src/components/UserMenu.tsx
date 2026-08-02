"use client";

import { useAuth } from "@/lib/auth";
import Link from "next/link";

export function UserMenu() {
  const { user, isAuthenticated, logout } = useAuth();

  if (!isAuthenticated || !user) {
    return (
      <Link
        href="/login"
        className="flex items-center gap-2 px-3 py-2 text-sm text-muted hover:text-white transition"
      >
        Sign in
      </Link>
    );
  }

  return (
    <div className="border-t border-border mt-2 pt-3 px-3 space-y-2">
      <div className="flex items-center gap-2">
        {user.github_avatar_url && (
          <img
            src={user.github_avatar_url}
            alt={user.github_login}
            className="w-7 h-7 rounded-full"
          />
        )}
        <div className="min-w-0">
          <div className="text-sm font-medium text-white truncate">
            {user.github_login}
          </div>
          <div className="text-xs text-muted capitalize">{user.role}</div>
        </div>
      </div>
      <div className="flex gap-2 text-xs">
        <Link href="/repos" className="text-accent hover:underline">
          My Repos
        </Link>
        <button
          onClick={logout}
          className="text-muted hover:text-err transition"
        >
          Logout
        </button>
      </div>
    </div>
  );
}
