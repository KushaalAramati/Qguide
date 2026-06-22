"use client";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { Card, Button } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function BuyPage() {
  return <Shell><BuyView /></Shell>;
}

function BuyView() {
  const { account, refresh } = useAuth();
  const [packages, setPackages] = useState<any[]>([]);
  const [perRun, setPerRun] = useState(5);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.packages().then((p) => { setPackages(p.packages); setPerRun(p.credits_per_run); }).catch(() => {});
  }, []);

  async function buy(pkg: any) {
    setBusy(true); setMsg("");
    try {
      await api.buy(pkg.credits, pkg.price, `${pkg.name} pack`);
      await refresh();
      setMsg(`✓ Added ${pkg.credits} credits (simulated payment).`);
    } catch (e: any) {
      setMsg(e.message || "Purchase failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="font-display font-extrabold text-3xl">Buy Credits</div>
      <div className="text-muted font-medium">
        Current balance: <b className="text-ink">💎 {account?.credits ?? 0} credits</b> · each design run costs {perRun} credits.
      </div>
      {msg && <div className="mt-3 text-good font-semibold">{msg}</div>}

      <div className="grid grid-cols-3 gap-5 mt-5">
        {packages.map((pkg) => (
          <Card key={pkg.name} className={`text-center ${pkg.popular ? "ring-2 ring-brand" : ""}`}>
            {pkg.popular && <div className="inline-block bg-brand text-white text-[10px] font-extrabold uppercase tracking-wide rounded-full px-2 py-0.5 mb-2">Most popular</div>}
            <div className="font-display font-extrabold text-lg">{pkg.name}</div>
            <div className="font-display font-extrabold text-4xl text-brand mt-1">{pkg.credits}</div>
            <div className="text-muted text-sm">credits</div>
            <div className="text-lg font-bold text-muted mt-2">${pkg.price}</div>
            <div className="text-sm text-muted mb-3">{pkg.sub}</div>
            <Button onClick={() => buy(pkg)} disabled={busy} variant={pkg.popular ? "primary" : "ghost"} full>Buy {pkg.name}</Button>
          </Card>
        ))}
      </div>
      <div className="mt-5 rounded-xl border border-brand/20 bg-brand/5 text-[#4a2a63] text-sm p-3">
        💳 Demo checkout — no real payment is processed. Structured to drop into Stripe later.
      </div>
    </div>
  );
}
