"use client";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { Card, Button } from "@/components/ui";
import { PageHeader, ErrorState } from "@/components/PageHeader";
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
      <PageHeader
        eyebrow="billing"
        title="Credits"
        description={`Each design run costs ${perRun} credits. Purchases are added to your balance immediately.`}
        actions={<span className="text-[11px] text-faint">balance <b className="text-ink font-medium">{account?.credits ?? 0}</b></span>}
      />
      {msg && (msg.startsWith("✓") ? <div className="mt-3 text-[11.5px] text-brand">{msg}</div> : <div className="mt-3"><ErrorState message={msg} /></div>)}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        {packages.map((pkg) => (
          <Card key={pkg.name} className={`text-center ${pkg.popular ? "!border-brand" : ""}`}>
            {pkg.popular && <div className="inline-block tag-good mb-2">most popular</div>}
            <div className="text-[13px] text-title font-medium">{pkg.name}</div>
            <div className="text-[32px] leading-none tracking-tightest tabular-nums text-brand mt-2">{pkg.credits}</div>
            <div className="label mt-1">credits</div>
            <div className="text-[16px] text-ink mt-3 tabular-nums">${pkg.price}</div>
            <div className="text-[11px] text-muted mb-3">{pkg.sub}</div>
            <Button onClick={() => buy(pkg)} disabled={busy} variant={pkg.popular ? "primary" : "ghost"} full>Buy {pkg.name}</Button>
          </Card>
        ))}
      </div>
      <div className="mt-4 caveat border border-warn/30">
        Simulated checkout — no payment is processed and no card is collected. A payment provider has not been connected yet.
      </div>
    </div>
  );
}
