"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, Account, setToken, getToken } from "./api";

interface AuthCtx {
  account: Account | null;
  ready: boolean;
  refresh: () => Promise<void>;
  signOut: () => void;
  setAccount: (a: Account | null) => void;
}

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);

  async function refresh() {
    if (!getToken()) {
      setAccount(null);
      setReady(true);
      return;
    }
    try {
      const a = await api.me();
      setAccount(a);
    } catch {
      setToken(null);
      setAccount(null);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function signOut() {
    setToken(null);
    setAccount(null);
    if (typeof window !== "undefined") window.location.href = "/login";
  }

  return (
    <Ctx.Provider value={{ account, ready, refresh, signOut, setAccount }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);

/** Redirects to /login when there is no authenticated account. */
export function useRequireAuth() {
  const { account, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready && !account) router.replace("/login");
  }, [ready, account, router]);
  return { account, ready };
}
