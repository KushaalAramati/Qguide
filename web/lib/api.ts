// Typed client for the backend API. Product naming lives in lib/branding.ts.
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

export type Role = "USER" | "RESEARCHER" | "ORGANIZATION_ADMIN" | "ADMIN";

export interface Account {
  name: string;
  email: string;
  plan: string;
  credits: number;
  runs: number;
  created: string;
  last_login?: string | null;
  is_admin?: boolean;
  role?: Role;
  status?: "active" | "suspended";
  permissions?: string[];
  institution?: string | null;
  research_area?: string | null;
  terms_accepted_at?: string | null;
  transactions: {
    ts: string;
    type: string;
    amount: number;
    balance: number;
    desc: string;
    price: number;
  }[];
}

export interface SignupInput {
  name: string;
  email: string;
  password: string;
  accept_terms: boolean;
  institution?: string;
  research_area?: string;
}

export const api = {
  signup: (input: SignupInput) =>
    req("/auth/signup", { method: "POST", body: JSON.stringify(input) }),
  branding: () => req("/branding"),
  health: () => req("/health"),
  legal: (slug: string) => req(`/legal/${slug}`),
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
  // Formula / QUBO upgrade endpoints (free; no credit charge)
  design: (request: any) => req("/design", { method: "POST", body: JSON.stringify(request) }),
  precisionPresets: () => req("/precision/presets"),
  optimizerCompare: (request: any, preset = "balanced", set_size?: number) =>
    req("/optimizer/compare", { method: "POST", body: JSON.stringify({ request, preset, set_size }) }),
  precisionExplain: (request: any, guide_id?: string) =>
    req("/precision/explain", { method: "POST", body: JSON.stringify({ request, guide_id }) }),
  // Auth / account management
  changePassword: (current_password: string, new_password: string) =>
    req("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password, new_password }) }),
  forgotPassword: (email: string) =>
    req("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, new_password: string) =>
    req("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }),
  updateProfile: (patch: { name?: string; institution?: string; research_area?: string }) =>
    req("/account/profile", { method: "PATCH", body: JSON.stringify(patch) }),
  // Folders / project organisation
  folders: () => req("/folders"),
  createFolder: (name: string, parent_id?: string | null) =>
    req("/folders", { method: "POST", body: JSON.stringify({ name, parent_id: parent_id ?? null }) }),
  renameFolder: (fid: string, name: string) =>
    req(`/folders/${fid}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteFolder: (fid: string) => req(`/folders/${fid}`, { method: "DELETE" }),
  patchProject: (pid: string, patch: { name?: string; folder_id?: string | null; archived?: boolean }) =>
    req(`/projects/${pid}`, { method: "PATCH", body: JSON.stringify(patch) }),
  // Admin (requires the caller's email to be in ADMIN_EMAILS on the server)
  adminUsers: () => req("/admin/users"),
  adminSetCredits: (email: string, credits: number) =>
    req("/admin/credits", { method: "POST", body: JSON.stringify({ email, credits }) }),
  adminRoles: () => req("/admin/roles"),
  adminStats: () => req("/admin/stats"),
  adminActivity: (limit = 50) => req(`/admin/activity?limit=${limit}`),
  adminHealth: () => req("/admin/health"),
  adminSetRole: (email: string, role: string) =>
    req("/admin/role", { method: "POST", body: JSON.stringify({ email, role }) }),
  adminSetStatus: (email: string, status: "active" | "suspended") =>
    req("/admin/status", { method: "POST", body: JSON.stringify({ email, status }) }),
};

export { BASE };
