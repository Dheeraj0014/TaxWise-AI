import type { TaxResult } from "../../lib/api";
import { inr } from "../../lib/api";

const ROWS: { label: string; key: keyof TaxResult; strong?: boolean }[] = [
  { label: "Gross total income", key: "gross_total_income" },
  { label: "Total deductions", key: "total_deductions" },
  { label: "Taxable income", key: "taxable_income" },
  { label: "Tax before rebate", key: "tax_before_rebate" },
  { label: "§87A rebate", key: "rebate_87a" },
  { label: "Capital-gains tax", key: "capital_gains_tax" },
  { label: "Surcharge", key: "surcharge" },
  { label: "Cess (4%)", key: "cess" },
  { label: "Total tax", key: "total_tax", strong: true },
];

export function ResultTable({ r, highlight }: { r: TaxResult; highlight?: boolean }) {
  const refund = Number(r.refund_or_due);
  return (
    <div
      className={`rounded-xl border p-5 ${
        highlight ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/20" : "border-slate-200 bg-white"
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-semibold capitalize">{r.regime} regime</h3>
        {highlight && (
          <span className="rounded-full bg-brand-600 px-2.5 py-0.5 text-xs font-medium text-white">
            Recommended
          </span>
        )}
      </div>
      <dl className="space-y-1.5 text-sm">
        {ROWS.map((row) => (
          <div
            key={row.key}
            className={`flex justify-between ${
              row.strong ? "mt-2 border-t border-slate-200 pt-2 text-base font-semibold" : ""
            }`}
          >
            <dt className="text-slate-500">{row.label}</dt>
            <dd className="tabular-nums">{inr(r[row.key] as string)}</dd>
          </div>
        ))}
        <div className="mt-2 flex justify-between border-t border-slate-200 pt-2">
          <dt className="text-slate-500">TDS / advance paid</dt>
          <dd className="tabular-nums">{inr(r.tds_paid)}</dd>
        </div>
        <div className="flex justify-between font-medium">
          <dt className={refund >= 0 ? "text-emerald-600" : "text-rose-600"}>
            {refund >= 0 ? "Refund" : "Payable"}
          </dt>
          <dd className={`tabular-nums ${refund >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
            {inr(Math.abs(refund))}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-[11px] text-slate-400">rules {r.rules_version}</p>
    </div>
  );
}
