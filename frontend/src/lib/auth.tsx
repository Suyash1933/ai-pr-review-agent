"use client";

import { createContext, useContext, useEffect, ReactNode } from "react";
import useSWR from "swr";
import { usePathname, useRouter } from "next/navigation";

export interface AuthUser {
  id: string;
  github_login: string;
  github_avatar_url: string;
  email: string | null;
  role: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  logout: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const PUBLIC_PATHS = ["/login"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const { data, error, isLoading, mutate } = useSWR<AuthUser>(
    "/api/v1/auth/me",
    async (url: string) => {
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Not authenticated");
      return res.json();
    },
    {
      revalidateOnFocus: true,
      shouldRetryOnError: false,
    }
  );

  const isAuthenticated = !!data && !error;

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !PUBLIC_PATHS.includes(pathname)) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  const logout = async () => {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    await mutate(undefined);
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user: data ?? null,
        isLoading,
        isAuthenticated,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
