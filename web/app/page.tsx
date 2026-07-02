"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { account, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!ready) return;
    router.replace(account ? "/new" : "/login");
  }, [ready, account, router]);
  return <div className="min-h-screen grid place-items-center text-muted">Loading…</div>;
}
