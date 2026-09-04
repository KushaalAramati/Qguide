"use client";
// /settings is the canonical name in navigation; the implementation lives at
// /account (kept so existing links and the notification deep links work).
import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function Redirect() {
  const router = useRouter();
  const params = useSearchParams();
  useEffect(() => { router.replace(`/account${params.toString() ? `?${params.toString()}` : ""}`); }, [router, params]);
  return null;
}
export default function SettingsPage() {
  return <Suspense fallback={null}><Redirect /></Suspense>;
}
