// Typed client for the Q-Guide FastAPI backend.
const BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("qg_token");
}
export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("qg_token", t);
  else localStorage.removeItem("qg_token");
}

async function req(path: string, opts: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((opts.headers as Record<string, string>) || {}),
  };
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(BASE + path, { ...opts, headers });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }));
    const err: any = new Error(
      typeof data.detail === "string" ? data.detail : "Request failed"
    );
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export interface Account {
  name: string;
  email: string;
  plan: string;
  credits: number;
  runs: number;
  created: string;
  last_login?: string | null;
  is_admin?: boolean;
  transactions: {
    ts: string;
    type: string;
    amount: number;
    balance: number;
    desc: string;
    price: number;
  }[];
}

export const api = {
  signup: (name: string, email: string, password: string) =>
    req("/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) }),
  login: (email: string, password: string) =>
    req("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: (): Promise<Account> => req("/me"),
  packages: () => req("/billing/packages"),
  buy: (credits: number, price: number, label: string) =>
    req("/credits/buy", { method: "POST", body: JSON.stringify({ credits, price, label }) }),
  enzymes: () => req("/enzymes"),
  projects: () => req("/projects"),
  project: (id: string) => req(`/projects/${id}`),
  deleteProject: (id: string) => req(`/projects/${id}`, { method: "DELETE" }),
  run: (request: any) => req("/run", { method: "POST", body: JSON.stringify({ request }) }),
  // Admin (requires the caller's email to be in ADMIN_EMAILS on the server)
  adminUsers: () => req("/admin/users"),
  adminSetCredits: (email: string, credits: number) =>
    req("/admin/credits", { method: "POST", body: JSON.stringify({ email, credits }) }),
};

export { BASE };
