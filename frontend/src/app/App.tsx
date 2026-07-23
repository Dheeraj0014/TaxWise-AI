// App shell: layout, navigation, AY selector and the auth gate (§9.2 app/).
import { useCallback, useEffect, useState } from "react";

import { Select } from "../components/ui";
import { api } from "../lib/api";
import { useSession } from "../store/session";
import { LoginPage } from "../features/auth/LoginPage";
import { CalculatorPage } from "../features/calculator/CalculatorPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { FinancesPage } from "../features/finances/FinancesPage";
import { RecommendationsPage } from "../features/optimizer/RecommendationsPage";
import { ProfilePage } from "../features/profile/ProfilePage";

type Route = "dashboard" | "finances" | "recommendations" | "calculator" | "profile";

const NAV: { route: Route; label: string; public?: boolean }[] = [
  { route: "dashboard", label: "Dashboard" },
  { route: "finances", label: "My finances" },
  { route: "recommendations", label: "Strategies" },
  { route: "calculator", label: "Calculator", public: true },
  { route: "profile", label: "Profile" },
];

/** Hash routing — enough for five views, and no dependency to install. */
function useHashRoute(fallback: Route): Route {
  const read = () => (location.hash.replace(/^#\/?/, "") || fallback) as Route;
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const onChange = () => setRoute(read());
    addEventListener("hashchange", onChange);
    return () => removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export default function App() {
  const { signedIn, email, signOut } = useSession();
  const route = useHashRoute(signedIn ? "dashboard" : "calculator");
  const [years, setYears] = useState<number[]>([2026, 2025]);
  const [ay, setAy] = useState(2026);
  // Bumped whenever stored data changes, so the dashboard refetches rather
  // than showing a position that no longer matches the finances page.
  const [revision, setRevision] = useState(0);
  const bump = useCallback(() => setRevision((r) => r + 1), []);

  useEffect(() => {
    api
      .assessmentYears()
      .then((ys) => {
        if (!ys.length) return;
        setYears([...ys].sort((a, b) => b - a));
        setAy((cur) => (ys.includes(cur) ? cur : ys[ys.length - 1]));
      })
      .catch(() => {});
  }, []);

  if (!signedIn && route !== "calculator") return <LoginPage />;

  const visible = NAV.filter((n) => signedIn || n.public);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
          <a href="#/dashboard" className="text-lg font-bold text-slate-900">
            AI Tax Optimizer <span className="text-brand-600">India</span>
          </a>

          <nav className="flex flex-wrap gap-1">
            {visible.map((n) => (
              <a
                key={n.route}
                href={`#/${n.route}`}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  route === n.route
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {n.label}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="w-40">
              <Select
                value={ay}
                onChange={setAy}
                options={years.map((y) => ({
                  value: y,
                  label: `AY ${y}-${String(y + 1).slice(2)}`,
                }))}
              />
            </div>
            {signedIn ? (
              <div className="flex items-center gap-2">
                <span
                  className="hidden max-w-[14rem] truncate text-sm text-slate-500 sm:inline"
                  title={email ?? undefined}
                >
                  {email}
                </span>
                <button
                  onClick={signOut}
                  className="text-sm font-medium text-slate-500 hover:text-slate-800"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <a
                href="#/dashboard"
                className="text-sm font-medium text-brand-600 hover:underline"
              >
                Sign in
              </a>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        {route === "dashboard" && <DashboardPage key={revision} ay={ay} />}
        {route === "finances" && <FinancesPage ay={ay} onChanged={bump} />}
        {route === "recommendations" && <RecommendationsPage ay={ay} />}
        {route === "calculator" && <CalculatorPage ay={ay} />}
        {route === "profile" && <ProfilePage years={years} onSaved={bump} />}
      </main>
    </div>
  );
}
