"use client";
import { Shell } from "@/components/Shell";
import { Card, CardTitle, Metric, Button } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

export default function AccountPage() {
  return <Shell><AccountView /></Shell>;
}

function AccountView() {
  const { account, signOut } = useAuth();
  if (!account) return null;
  const used = account.transactions.filter((t) => t.type === "usage").reduce((s, t) => s - t.amount, 0);

  return (
    <div>
      <div className="font-display font-extrabold text-3xl">Account</div>
      <div className="text-muted font-medium">{account.name} · {account.email}</div>

      <div className="grid grid-cols-4 gap-4 mt-4">
        <Metric label="Credit balance" value={`💎 ${account.credits}`} sub="available" color="brand" />
        <Metric label="Plan" value={account.plan} sub={`since ${account.created.slice(0, 10)}`} />
        <Metric label="Design runs" value={account.runs} sub={`${used} credits used`} color="good" />
        <Metric label="Transactions" value={account.transactions.length} sub="this account" />
      </div>

      <div className="grid grid-cols-[1.5fr_1fr] gap-5 mt-5">
        <Card>
          <CardTitle>Transaction history</CardTitle>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead><tr className="text-muted text-left text-xs uppercase">
                {["When", "Type", "Credits", "Balance", "Detail", "Paid"].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}
              </tr></thead>
              <tbody>
                {[...account.transactions].reverse().map((t, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{t.ts}</td>
                    <td className="pr-3 capitalize">{t.type}</td>
                    <td className={`pr-3 font-bold ${t.amount >= 0 ? "text-good" : "text-bad"}`}>{t.amount >= 0 ? "+" : ""}{t.amount}</td>
                    <td className="pr-3">{t.balance}</td>
                    <td className="pr-3">{t.desc}</td>
                    <td className="pr-3">{t.price ? `$${t.price.toFixed(2)}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card>
          <CardTitle>Profile</CardTitle>
          <div className="text-sm"><b>Name:</b> {account.name}</div>
          <div className="text-sm mt-1"><b>Email:</b> {account.email}</div>
          <div className="mt-4 flex flex-col gap-2">
            <Link href="/buy"><Button full>💳 Buy more credits</Button></Link>
            <Button variant="ghost" onClick={signOut} full>↪ Log out</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
