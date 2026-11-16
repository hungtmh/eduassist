"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { SWRConfig } from "swr";
import { ToastProvider } from "@/components/ui";
import { api, fetcher, getToken, setToken } from "@/lib/api";

export type Profile = {
  username: string;
  role: "student" | "consultant" | "academic" | "accountant" | "teacher" | "manager";
  role_label: string;
  display_name: string;
  hoc_vien_id: number | null;
  giang_vien_id: number | null;
  permissions: string[];
  must_change_password: boolean;
};

type AuthState = {
  user: Profile | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<Profile>;
  logout: () => void;
  can: (perm: string) => boolean;
};

const AuthCtx = createContext<AuthState>(null as unknown as AuthState);
export const useAuth = () => useContext(AuthCtx);

export function homeFor(u: Profile): string {
  if (u.must_change_password) return "/doi-mat-khau";
  if (u.role === "student") return "/portal";
  if (u.role === "manager") return "/dashboard";
  return "/hom-nay"; // tư vấn, giáo vụ, kế toán, giảng viên: việc của chính mình hôm nay
}

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api<Profile>("/me/profile")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const r = await api<{ access_token: string }>("/auth/login", { body: { username, password } });
    setToken(r.access_token);
    const p = await api<Profile>("/me/profile");
    setUser(p);
    return p;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  const can = useCallback((perm: string) => !!user?.permissions.includes(perm), [user]);

  return <AuthCtx.Provider value={{ user, loading, login, logout, can }}>{children}</AuthCtx.Provider>;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: true, shouldRetryOnError: false }}>
      <ToastProvider>
        <AuthProvider>{children}</AuthProvider>
      </ToastProvider>
    </SWRConfig>
  );
}
