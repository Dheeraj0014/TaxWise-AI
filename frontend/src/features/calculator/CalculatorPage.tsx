// Ad-hoc calculator (§4 Tax calculation). Works signed-out: nothing here is
// persisted, so anyone can price a scenario without handing over financial data.
import { useState } from "react";

import {
  Alert,
  Button,
  Card,
  Disclaimer,
  Empty,
  Field,
  NumInput,
} from "../../components/ui";
import { api, inr, type CompareResult, type OptimizerResult } from "../../lib/api";
import { ResultTable } from "./ResultTable";

const DEDUCTION_SECTIONS = [
  { key: "80C", label: "80C (PPF/ELSS/EPF)" },
  { key: "80CCD1B", label: "80CCD(1B) NPS" },
  { key: "80D", label: "80D health insurance" },
  { key: "24b", label: "24(b) home-loan interest" },
  { key: "hra_exempt", label: "HRA exemption" },
];

export function CalculatorPage({ ay }: { ay: number }) {
  const [salary, setSalary] = useState(1800000);
  const [other, setOther] = useState(0);
  const [tds, setTds] = useState(0);
  const [deductions, setDeductions] = useState<Record<string, number>>({
    "80C": 150000,
    "80CCD1B": 50000,
    "80D": 25000,
  });
  const [result, setResult] = useState<CompareResult | null>(null);
  const [optimizer, setOptimizer] = useState<OptimizerResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    const payload = {
      assessment_year: ay,
      regime: "new" as const,
      income: { salary_gross: salary, other },
      deductions,
      tds_paid: tds,
    };
    try {
      const [cmp, opt] = await Promise.all([
        api.compare(payload),
        api.optimize({ ...payload, regime: "old" }),
      ]);
      setResult(cmp);
      setOptimizer(opt);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-[340px_1fr]">
      <Card title="Your figures" className="h-fit">
        <div className="space-y-4">
          <Field label="Gross salary">
            <NumInput value={salary} onChange={setSalary} />
          </Field>
          <Field label="Other income">
            <NumInput value={other} onChange={setOther} />
          </Field>
          <Field label="TDS / advance tax paid">
            <NumInput value={tds} onChange={setTds} />
          </Field>

          <div className="border-t border-slate-100 pt-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Deductions (old regime)
            </p>
            <div className="space-y-2">
              {DEDUCTION_SECTIONS.map((s) => (
                <Field key={s.key} label={s.label} small>
                  <NumInput
                    value={deductions[s.key] ?? 0}
                    onChange={(v) =>
                      setDeductions((d) => ({ ...d, [s.key]: v }))
                    }
                  />
                </Field>
              ))}
            </div>
          </div>

          <Button onClick={run} disabled={loading} className="w-full">
            {loading ? "Calculating…" : "Compare regimes"}
          </Button>
          {error && <Alert>{error}</Alert>}
        </div>
      </Card>

      <section className="space-y-5">
        {!result && !loading && <Empty>Enter your figures and compare.</Empty>}

        {result && (
          <>
            <div className="rounded-xl border border-brand-200 bg-gradient-to-br from-brand-50 to-white p-4">
              <p className="text-sm text-slate-600">
                Recommended:{" "}
                <span className="font-semibold capitalize text-brand-700">
                  {result.recommended_regime} regime
                </span>{" "}
                — saves {inr(result.savings_vs_alternative)} vs the alternative.
              </p>
              <p className="mt-1 text-xs text-slate-500">{result.note}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <ResultTable
                r={result.old_regime}
                highlight={result.recommended_regime === "old"}
              />
              <ResultTable
                r={result.new_regime}
                highlight={result.recommended_regime === "new"}
              />
            </div>

            {optimizer && optimizer.recommendations.length > 0 && (
              <Card
                title="Tax-saving ideas"
                actions={
                  <span className="text-sm font-normal text-emerald-600">
                    up to {inr(optimizer.total_potential_saving)}
                  </span>
                }
              >
                <ul className="space-y-3">
                  {optimizer.recommendations.map((rec) => (
                    <li
                      key={rec.section}
                      className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 p-3"
                    >
                      <div>
                        <p className="font-medium text-slate-800">{rec.title}</p>
                        <p className="text-xs text-slate-500">{rec.note}</p>
                        {rec.deadline && (
                          <p className="mt-0.5 text-xs text-amber-600">
                            Deadline: {rec.deadline}
                          </p>
                        )}
                      </div>
                      <span className="whitespace-nowrap rounded-md bg-emerald-100 px-2 py-1 text-sm font-semibold text-emerald-700">
                        {inr(rec.estimated_saving)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}

        <Disclaimer />
      </section>
    </div>
  );
}
