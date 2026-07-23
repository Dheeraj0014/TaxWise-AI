import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Bar,
  Card,
  Disclaimer,
  Empty,
  Field,
  NumInput,
  Stat,
} from "../../components/ui";
import { api, inr, type DashboardSummary, type Forecast } from "../../lib/api";
import { ResultTable } from "../calculator/ResultTable";

const INCOME_COLORS: Record<string, string> = {
  salary: "bg-brand-500",
  rental: "bg-emerald-500",
  business: "bg-amber-500",
  other: "bg-slate-400",
};

export function DashboardPage({ ay }: { ay: number }) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [growth, setGrowth] = useState(10);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, f] = await Promise.all([api.summary(ay), api.forecast(ay, growth)]);
      setSummary(s);
      setForecast(f);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [ay, growth]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !summary) return <Empty>Loading your position…</Empty>;
  if (error) return <Alert>{error}</Alert>;
  if (!summary) return null;

  if (!summary.has_data) {
    return (
      <Empty>
        No income recorded for AY {summary.assessment_year}-
        {String(summary.assessment_year + 1).slice(2)} yet.
        <br />
        Add your income and investments under{" "}
        <a href="#/finances" className="text-brand-600 hover:underline">
          My finances
        </a>{" "}
        to see your position.
      </Empty>
    );
  }

  const h = summary.headline;
  const refund = Number(h.refund_or_due);
  const incomeItems = Object.entries(summary.income_breakdown).map(
    ([label, value]) => ({
      label,
      value,
      color: INCOME_COLORS[label] ?? "bg-slate-400",
    }),
  );
  const deductionItems = Object.entries(summary.deduction_breakdown).map(
    ([label, value], i) => ({
      label,
      value: Number(value),
      color: ["bg-brand-500", "bg-emerald-500", "bg-amber-500", "bg-violet-500",
        "bg-sky-500", "bg-rose-400"][i % 6],
    }),
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Gross total income" value={inr(h.gross_total_income)} />
        <Stat label="Taxable income" value={inr(h.taxable_income)} />
        <Stat
          label="Total tax"
          value={inr(h.total_tax)}
          sub={`${summary.recommended_regime} regime · ${summary.rules_version}`}
        />
        <Stat
          label={refund >= 0 ? "Refund due" : "Tax payable"}
          value={inr(Math.abs(refund))}
          tone={refund >= 0 ? "good" : "bad"}
          sub={`TDS paid ${inr(h.tds_paid)}`}
        />
      </div>

      <Card
        title={`Recommended: ${summary.recommended_regime} regime`}
        actions={
          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-sm font-semibold text-emerald-700">
            saves {inr(summary.savings_vs_alternative)}
          </span>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <ResultTable
            r={summary.old_regime}
            highlight={summary.recommended_regime === "old"}
          />
          <ResultTable
            r={summary.new_regime}
            highlight={summary.recommended_regime === "new"}
          />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Income composition">
          <Bar items={incomeItems} />
          <dl className="mt-4 space-y-1.5 text-sm">
            {incomeItems.map((i) => (
              <div key={i.label} className="flex justify-between">
                <dt className="capitalize text-slate-500">{i.label}</dt>
                <dd className="tabular-nums">{inr(i.value)}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Deductions claimed">
          {deductionItems.length === 0 ? (
            <Empty>No deductions recorded.</Empty>
          ) : (
            <>
              <Bar items={deductionItems} />
              <dl className="mt-4 space-y-1.5 text-sm">
                {deductionItems.map((i) => (
                  <div key={i.label} className="flex justify-between">
                    <dt className="text-slate-500">§{i.label}</dt>
                    <dd className="tabular-nums">{inr(i.value)}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs text-slate-400">
                Claimed totals. The engine applies each section's statutory cap —
                see the old-regime breakdown above for what was actually allowed.
              </p>
            </>
          )}
        </Card>
      </div>

      {summary.capital_gains.length > 0 && (
        <Card title="Capital gains">
          <dl className="space-y-1.5 text-sm">
            {summary.capital_gains.map((g) => (
              <div key={g.tax_section} className="flex justify-between">
                <dt className="text-slate-500">§{g.tax_section}</dt>
                <dd className="tabular-nums">{inr(g.amount)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-slate-400">
            Taxed at special rates and excluded from the §87A rebate base.
          </p>
        </Card>
      )}

      {forecast && (
        <Card title="Forecast">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-36">
              <Field label="Income growth %" small>
                <NumInput value={growth} onChange={setGrowth} min={-100} step={1} />
              </Field>
            </div>
            <div className="flex-1 text-sm">
              <p className="text-slate-700">
                At {forecast.growth_pct}% growth, tax moves from{" "}
                <span className="font-semibold tabular-nums">
                  {inr(forecast.current_tax)}
                </span>{" "}
                to{" "}
                <span className="font-semibold tabular-nums">
                  {inr(forecast.projected_tax)}
                </span>{" "}
                <span
                  className={
                    Number(forecast.delta) >= 0 ? "text-rose-600" : "text-emerald-600"
                  }
                >
                  ({Number(forecast.delta) >= 0 ? "+" : ""}
                  {inr(forecast.delta)})
                </span>
                .
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {forecast.same_year_rules_reused
                  ? `No rate table published beyond AY ${forecast.base_assessment_year}, so this reuses ${forecast.projected_with_rules_version}. `
                  : `Projected against ${forecast.projected_with_rules_version}. `}
                {forecast.note}
              </p>
            </div>
          </div>
        </Card>
      )}

      <Disclaimer />
    </div>
  );
}
