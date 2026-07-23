// API client for the tax backend (§9.2 lib/api client).
//
// Money crosses the wire as a *string*, never a JS number: the backend computes
// in Decimal and 2^53 rounding has no place in a tax figure. Format with `inr`
// at the edge; only compare/sort after an explicit Number() where precision
// genuinely does not matter (e.g. is this a refund or a payable).

import { getToken, setToken } from "./auth";

const BASE = "/api/v1";

// --- Core result shapes ------------------------------------------------------

export interface TaxResult {
  regime: string;
  rules_version: string;
  gross_total_income: string;
  total_deductions: string;
  taxable_income: string;
  tax_before_rebate: string;
  rebate_87a: string;
  tax_after_rebate: string;
  capital_gains_tax: string;
  surcharge: string;
  marginal_relief: string;
  cess: string;
  total_tax: string;
  tds_paid: string;
  refund_or_due: string;
  breakdown: { deductions: Record<string, string>; capital_gains: unknown[] };
}

export interface CompareResult {
  assessment_year: number;
  rules_version: string;
  old_regime: TaxResult;
  new_regime: TaxResult;
  recommended_regime: "old" | "new";
  savings_vs_alternative: string;
  note: string;
}

/** What an idea does to your money — drives grouping and ranking, not styling. */
export type IdeaKind = "expense" | "structural" | "invest" | "donate";

export interface Recommendation {
  title: string;
  section: string;
  kind: IdeaKind;
  estimated_saving: string;
  amount_modelled: string;
  /** Cash you never get back. Non-zero only for donations. */
  net_cost: string;
  headroom?: string | null;
  retained?: boolean;
  /** True when the amount is a modelled unit, not a computed cap headroom. */
  illustrative?: boolean;
  priority: number;
  required_documents: string[];
  deadline: string | null;
  note: string;
}

export interface OptimizerResult {
  recommendations: Recommendation[];
  /** Excludes donations — see donation_relief. */
  total_potential_saving: number;
  donation_relief: number;
  disclaimer: string;
}

export interface CalcPayload {
  assessment_year: number;
  regime: "old" | "new";
  income: { salary_gross: number; rental?: number; other?: number; business?: number };
  deductions: Record<string, number>;
  capital_gains?: { tax_section: string; amount: number }[];
  tds_paid: number;
}

// --- Stored financial heads (§3 ERD) ----------------------------------------

export type IncomeRow = {
  id: string;
  type: "salary" | "business" | "rental" | "other";
  gross_amount: string;
  exemptions: string;
  tds_paid: string;
  assessment_year: number;
}

export type DeductionRow = {
  id: string;
  section: string;
  claimed_amount: string;
  assessment_year: number;
}

export type InvestmentRow = {
  id: string;
  instrument: "PPF" | "ELSS" | "NPS" | "MF" | "EQUITY";
  amount: string;
  section: string;
  invested_on: string | null;
  assessment_year: number;
}

export type LoanRow = {
  id: string;
  type: "home" | "education";
  principal_paid: string;
  interest_paid: string;
  section: string;
  assessment_year: number;
}

export type InsuranceRow = {
  id: string;
  type: "life" | "health";
  premium: string;
  section: string;
  for_senior_citizen: boolean;
  assessment_year: number;
}

export type CapitalGainRow = {
  id: string;
  asset_class: "equity" | "debt" | "property";
  term: "STCG" | "LTCG";
  amount: string;
  tax_section: string;
  assessment_year: number;
}

export type StoredRecommendation = {
  id: string;
  computation_id: string;
  title: string;
  section: string;
  estimated_saving: string;
  kind: IdeaKind;
  amount_modelled: string;
  net_cost: string;
  priority: number;
  required_documents: string[];
  deadline: string | null;
  note: string | null;
  status: "suggested" | "accepted" | "dismissed";
}

// --- Dashboard --------------------------------------------------------------

export interface DashboardSummary {
  assessment_year: number;
  rules_version: string;
  has_data: boolean;
  income_breakdown: Record<string, number>;
  deduction_breakdown: Record<string, string>;
  capital_gains: { tax_section: string; amount: string }[];
  old_regime: TaxResult;
  new_regime: TaxResult;
  recommended_regime: "old" | "new";
  savings_vs_alternative: string;
  headline: {
    gross_total_income: string;
    total_deductions: string;
    taxable_income: string;
    total_tax: string;
    tds_paid: string;
    refund_or_due: string;
  };
  disclaimer: string;
}

export interface Forecast {
  base_assessment_year: number;
  projected_assessment_year: number;
  projected_with_rules_version: string;
  same_year_rules_reused: boolean;
  growth_pct: string;
  current_tax: string;
  projected_tax: string;
  delta: string;
  recommended_regime: "old" | "new";
  note: string;
}

export interface Profile {
  full_name: string | null;
  pan_masked: string | null;
  age: number | null;
  residential_status: string;
  preferred_regime: string | null;
  assessment_year: number;
  locale: string;
}

// --- Transport --------------------------------------------------------------

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (auth && token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (res.status === 401 || res.status === 403) {
    // Expired or missing session — drop it so the app returns to the login gate.
    if (auth && token) setToken(null);
    throw new ApiError(res.status, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body.detail ?? body.title ?? body;
    if (typeof detail === "string") return detail;
    // FastAPI 422 gives a list of {loc, msg}; surface the first usefully.
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      const field = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
      return field ? `${field}: ${first.msg}` : first.msg;
    }
    return JSON.stringify(detail);
  } catch {
    return `Request failed (${res.status})`;
  }
}

const get = <T>(p: string, params?: Record<string, string | number | undefined>) => {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== "")
          .map(([k, v]) => [k, String(v)]),
      )
    : "";
  return request<T>(`${p}${qs}`);
};
const post = <T>(p: string, body?: unknown) =>
  request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const del = (p: string) => request<void>(p, { method: "DELETE" });

// --- Public surface ---------------------------------------------------------

export const api = {
  // auth (§4 Auth)
  register: (email: string, password: string) =>
    request<unknown>(
      "/auth/register",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),
  login: async (email: string, password: string) => {
    const t = await request<{ access_token: string }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    );
    setToken(t.access_token);
    return t;
  },
  logout: () => setToken(null),
  me: () => get<{ id: string; email: string; role: string }>("/auth/me"),

  // profile
  getProfile: () => get<Profile>("/profile"),
  updateProfile: (p: Partial<Profile> & { pan?: string }) =>
    request<Profile>("/profile", { method: "PUT", body: JSON.stringify(p) }),

  // stateless calculator (§4 Tax calculation) — no auth required
  compare: (p: CalcPayload) =>
    request<CompareResult>(
      "/tax/compare",
      { method: "POST", body: JSON.stringify(p) },
      false,
    ),
  optimize: (p: CalcPayload) =>
    request<OptimizerResult>(
      "/optimizer/recommend",
      { method: "POST", body: JSON.stringify(p) },
      false,
    ),
  assessmentYears: async () =>
    (await request<{ available: number[] }>("/tax/assessment-years", {}, false))
      .available,

  // financial heads (§4 Profile & finances)
  income: crud<IncomeRow>("/income"),
  deductions: crud<DeductionRow>("/deductions"),
  investments: crud<InvestmentRow>("/investments"),
  loans: crud<LoanRow>("/loans"),
  insurance: crud<InsuranceRow>("/insurance"),
  capitalGains: crud<CapitalGainRow>("/capital-gains"),

  // dashboard (§4 dashboard)
  summary: (ay?: number) => get<DashboardSummary>("/dashboard/summary", { assessment_year: ay }),
  forecast: (ay?: number, growth_pct = 10) =>
    get<Forecast>("/dashboard/forecast", { assessment_year: ay, growth_pct }),

  // persisted recommendations
  generateRecommendations: (ay?: number) =>
    post<StoredRecommendation[]>(
      `/recommendations/generate${ay ? `?assessment_year=${ay}` : ""}`,
    ),
  listRecommendations: (status?: string) =>
    get<StoredRecommendation[]>("/recommendations", { status }),
  patchRecommendation: (id: string, status: StoredRecommendation["status"]) =>
    request<StoredRecommendation>(`/recommendations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};

/** The six financial heads share one shape, so they share one client. */
function crud<T extends { id: string }>(path: string) {
  return {
    list: (assessment_year?: number) => get<T[]>(path, { assessment_year }),
    add: (body: Record<string, unknown>) => post<T>(path, body),
    remove: (id: string) => del(`${path}/${id}`),
  };
}

// --- Formatting -------------------------------------------------------------

export const inr = (v: string | number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(v));
