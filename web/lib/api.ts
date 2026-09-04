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
    // FastAPI validation errors arrive as a list of {loc, msg}; surface the first
    // one as a readable sentence instead of a generic "Request failed".
    let message = "Request failed";
    if (typeof data.detail === "string") message = data.detail;
    else if (Array.isArray(data.detail) && data.detail.length) {
      const d = data.detail[0];
      const field = Array.isArray(d.loc) ? d.loc.filter((x: any) => x !== "body").join(".") : "";
      const msg = String(d.msg || "").replace(/^value error, /i, "");
      message = field ? `${field}: ${msg}` : msg || message;
    }
    const err: any = new Error(message);
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
  onboarding?: { completed: boolean; step: number; completed_at?: string | null };
  transactions: {
    ts: string;
    type: string;
    amount: number;
    balance: number;
    desc: string;
    price: number;
  }[];
}

export type ProjectRole = "OWNER" | "EDITOR" | "VIEWER";

export interface ProjectAccess {
  role: ProjectRole;
  uid: string;
  owner_email: string;
  is_owner: boolean;
  can_view: boolean; can_edit: boolean; can_run: boolean;
  can_share: boolean; can_delete: boolean; can_organize: boolean;
}

export interface ProjectMember {
  email: string;
  name: string;
  role: ProjectRole;
  invited_by?: string | null;
  created: string;
}

/** Project list row: own projects carry role OWNER; shared ones carry the caller's role. */
export interface ProjectMeta {
  id: string;
  uid: string | null;
  name: string;
  created: string;
  n_guides?: number | null;
  best_guide?: string | null;
  folder_id?: string | null;
  archived?: boolean;
  owner_email: string;
  owner_name?: string;
  role: ProjectRole;
  shared: boolean;
  n_collaborators?: number;
}

/** Route for a project row: owners use their short pid, collaborators the global uid. */
export function projectHref(p: { id: string; uid?: string | null; shared?: boolean }) {
  return `/project/${p.shared && p.uid ? p.uid : p.id}`;
}

export interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  link?: string | null;
  read: boolean;
  created: string;
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
  projects: (): Promise<ProjectMeta[]> => req("/projects"),
  projectMembers: (id: string) => req(`/projects/${id}/members`),
  inviteMember: (id: string, email: string, role: "EDITOR" | "VIEWER") =>
    req(`/projects/${id}/members`, { method: "POST", body: JSON.stringify({ email, role }) }),
  setMemberRole: (id: string, email: string, role: "EDITOR" | "VIEWER") =>
    req(`/projects/${id}/members/${encodeURIComponent(email)}`, { method: "PATCH", body: JSON.stringify({ role }) }),
  removeMember: (id: string, email: string) =>
    req(`/projects/${id}/members/${encodeURIComponent(email)}`, { method: "DELETE" }),
  lookupUser: (email: string) => req(`/users/lookup?email_q=${encodeURIComponent(email)}`),
  rerunProject: (id: string, overrides?: Record<string, any>) =>
    req(`/projects/${id}/rerun`, { method: "POST", body: JSON.stringify({ overrides: overrides ?? null }) }),
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
  onboarding: () => req("/account/onboarding"),
  updateOnboarding: (patch: { step?: number; completed?: boolean }) =>
    req("/account/onboarding", { method: "PATCH", body: JSON.stringify(patch) }),
  updateProfile: (patch: { name?: string; institution?: string; research_area?: string }) =>
    req("/account/profile", { method: "PATCH", body: JSON.stringify(patch) }),
  // Folders / project organisation
  folders: () => req("/folders"),
  createFolder: (name: string, parent_id?: string | null) =>
    req("/folders", { method: "POST", body: JSON.stringify({ name, parent_id: parent_id ?? null }) }),
  renameFolder: (fid: string, name: string) =>
    req(`/folders/${fid}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteFolder: (fid: string) => req(`/folders/${fid}`, { method: "DELETE" }),
  patchProject: (pid: string, patch: { name?: string; folder_id?: string | null; archived?: boolean; selected_guide?: string }) =>
    req(`/projects/${pid}`, { method: "PATCH", body: JSON.stringify(patch) }),
  // Notifications
  notifications: (limit = 30, unreadOnly = false): Promise<{ items: Notification[]; unread: number }> =>
    req(`/notifications?limit=${limit}&unread_only=${unreadOnly}`),
  unreadCount: (): Promise<{ unread: number }> => req("/notifications/unread-count"),
  markRead: (id: number) => req(`/notifications/${id}/read`, { method: "POST" }),
  markUnread: (id: number) => req(`/notifications/${id}/unread`, { method: "POST" }),
  markAllRead: () => req("/notifications/read-all", { method: "POST" }),
  deleteNotification: (id: number) => req(`/notifications/${id}`, { method: "DELETE" }),
  notificationPrefs: () => req("/account/notification-preferences"),
  setNotificationPrefs: (preferences: Record<string, boolean>) =>
    req("/account/notification-preferences", { method: "PATCH", body: JSON.stringify({ preferences }) }),
  // Research tools
  projectMetadata: (id: string) => req(`/research/projects/${id}/metadata`),
  patchProjectMetadata: (id: string, patch: Record<string, any>) =>
    req(`/research/projects/${id}/metadata`, { method: "PATCH", body: JSON.stringify(patch) }),
  researchTags: () => req("/research/tags"),
  templates: () => req("/research/templates"),
  createTemplate: (name: string, description: string, params: Record<string, any>) =>
    req("/research/templates", { method: "POST", body: JSON.stringify({ name, description, params }) }),
  updateTemplate: (id: number, patch: { name?: string; description?: string; params?: Record<string, any> }) =>
    req(`/research/templates/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteTemplate: (id: number) => req(`/research/templates/${id}`, { method: "DELETE" }),
  batchLimits: () => req("/research/batch/limits"),
  runBatch: (body: { targets: { name: string; sequence: string }[]; params?: Record<string, any>; template_id?: number | null; folder_name?: string; tags?: string[]; experiment_name?: string }) =>
    req("/research/batch", { method: "POST", body: JSON.stringify(body) }),
  compareProjects: (project_ids: string[]) =>
    req("/research/compare", { method: "POST", body: JSON.stringify({ project_ids }) }),
  researchHistory: (limit = 50) => req(`/research/history?limit=${limit}`),
  projectReport: (id: string) => req(`/research/projects/${id}/report`),
  projectReportMarkdown: async (id: string): Promise<string> => {
    const t = getToken();
    const res = await fetch(`${BASE}/research/projects/${id}/report?fmt=md`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
    if (!res.ok) throw new Error("Could not build the report.");
    return res.text();
  },
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
