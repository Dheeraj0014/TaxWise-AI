// CRUD for the six financial heads (§4 Profile & finances).
//
// Every head is the same interaction — a table of rows plus one add-form — so
// they are described as data (`HEADS`) and rendered by one component, mirroring
// the `_register_crud` factory that serves them on the backend.
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Card,
  Empty,
  Field,
  NumInput,
  Select,
} from "../../components/ui";
import { api, inr } from "../../lib/api";

type FieldSpec =
  | { key: string; label: string; kind: "money"; default?: number }
  | { key: string; label: string; kind: "select"; options: string[]; default?: string }
  | { key: string; label: string; kind: "bool"; default?: boolean };

interface HeadSpec {
  key: string;
  title: string;
  blurb: string;
  client: {
    list: (ay?: number) => Promise<Record<string, unknown>[]>;
    add: (b: Record<string, unknown>) => Promise<unknown>;
    remove: (id: string) => Promise<void>;
  };
  fields: FieldSpec[];
  /** Columns shown in the table, in order. */
  columns: { key: string; label: string; money?: boolean }[];
}

const DEDUCTION_SECTIONS = [
  "80C", "80CCD1B", "80CCD2", "80D", "80E", "80EEA", "24b",
  "hra_exempt", "80G", "80TTA", "80TTB",
];

const HEADS: HeadSpec[] = [
  {
    key: "income",
    title: "Income",
    blurb: "Salary, rental, business and other heads. TDS here drives your refund.",
    client: api.income as HeadSpec["client"],
    fields: [
      { key: "type", label: "Type", kind: "select",
        options: ["salary", "rental", "business", "other"], default: "salary" },
      { key: "gross_amount", label: "Gross amount", kind: "money" },
      { key: "exemptions", label: "Exemptions", kind: "money" },
      { key: "tds_paid", label: "TDS paid", kind: "money" },
    ],
    columns: [
      { key: "type", label: "Type" },
      { key: "gross_amount", label: "Gross", money: true },
      { key: "exemptions", label: "Exempt", money: true },
      { key: "tds_paid", label: "TDS", money: true },
    ],
  },
  {
    key: "investments",
    title: "Investments",
    blurb: "PPF, ELSS, NPS and similar — each claims a Chapter VI-A section.",
    client: api.investments as HeadSpec["client"],
    fields: [
      { key: "instrument", label: "Instrument", kind: "select",
        options: ["PPF", "ELSS", "NPS", "MF", "EQUITY"], default: "ELSS" },
      { key: "amount", label: "Amount", kind: "money" },
      { key: "section", label: "Section", kind: "select",
        options: DEDUCTION_SECTIONS, default: "80C" },
    ],
    columns: [
      { key: "instrument", label: "Instrument" },
      { key: "section", label: "Section" },
      { key: "amount", label: "Amount", money: true },
    ],
  },
  {
    key: "insurance",
    title: "Insurance",
    blurb: "Life premiums claim 80C; health premiums claim 80D.",
    client: api.insurance as HeadSpec["client"],
    fields: [
      { key: "type", label: "Type", kind: "select",
        options: ["health", "life"], default: "health" },
      { key: "premium", label: "Premium", kind: "money" },
      { key: "section", label: "Section", kind: "select",
        options: ["80D", "80C"], default: "80D" },
      { key: "for_senior_citizen", label: "For a senior citizen", kind: "bool" },
    ],
    columns: [
      { key: "type", label: "Type" },
      { key: "section", label: "Section" },
      { key: "premium", label: "Premium", money: true },
    ],
  },
  {
    key: "loans",
    title: "Loans",
    blurb: "Interest claims 24(b)/80E; principal claims 80C.",
    client: api.loans as HeadSpec["client"],
    fields: [
      { key: "type", label: "Type", kind: "select",
        options: ["home", "education"], default: "home" },
      { key: "principal_paid", label: "Principal paid", kind: "money" },
      { key: "interest_paid", label: "Interest paid", kind: "money" },
      { key: "section", label: "Section", kind: "select",
        options: ["24b", "80E", "80EEA", "80C"], default: "24b" },
    ],
    columns: [
      { key: "type", label: "Type" },
      { key: "section", label: "Section" },
      { key: "principal_paid", label: "Principal", money: true },
      { key: "interest_paid", label: "Interest", money: true },
    ],
  },
  {
    key: "deductions",
    title: "Other deductions",
    blurb: "Anything claimed directly rather than via an investment or premium.",
    client: api.deductions as HeadSpec["client"],
    fields: [
      { key: "section", label: "Section", kind: "select",
        options: DEDUCTION_SECTIONS, default: "80D" },
      { key: "claimed_amount", label: "Claimed amount", kind: "money" },
    ],
    columns: [
      { key: "section", label: "Section" },
      { key: "claimed_amount", label: "Claimed", money: true },
    ],
  },
  {
    key: "capital-gains",
    title: "Capital gains",
    blurb: "Taxed at special rates, outside the §87A rebate base.",
    client: api.capitalGains as HeadSpec["client"],
    fields: [
      { key: "asset_class", label: "Asset class", kind: "select",
        options: ["equity", "debt", "property"], default: "equity" },
      { key: "term", label: "Term", kind: "select",
        options: ["LTCG", "STCG"], default: "LTCG" },
      { key: "amount", label: "Gain", kind: "money" },
      { key: "tax_section", label: "Section", kind: "select",
        options: ["112A", "111A", "112"], default: "112A" },
    ],
    columns: [
      { key: "asset_class", label: "Asset" },
      { key: "term", label: "Term" },
      { key: "tax_section", label: "Section" },
      { key: "amount", label: "Gain", money: true },
    ],
  },
];

export function FinancesPage({
  ay,
  onChanged,
}: {
  ay: number;
  onChanged?: () => void;
}) {
  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">
        Everything recorded here feeds the dashboard and the optimizer for AY {ay}-
        {String(ay + 1).slice(2)}. Amounts are totals for the year.
      </p>
      {HEADS.map((head) => (
        <HeadCard key={head.key} head={head} ay={ay} onChanged={onChanged} />
      ))}
    </div>
  );
}

function initialDraft(head: HeadSpec): Record<string, unknown> {
  const draft: Record<string, unknown> = {};
  for (const f of head.fields) {
    if (f.kind === "money") draft[f.key] = f.default ?? 0;
    else if (f.kind === "bool") draft[f.key] = f.default ?? false;
    else draft[f.key] = f.default ?? f.options[0];
  }
  return draft;
}

function HeadCard({
  head,
  ay,
  onChanged,
}: {
  head: HeadSpec;
  ay: number;
  onChanged?: () => void;
}) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [draft, setDraft] = useState(() => initialDraft(head));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await head.client.list(ay));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [head, ay]);

  useEffect(() => {
    void load();
  }, [load]);

  async function add() {
    setBusy(true);
    setError(null);
    try {
      await head.client.add({ ...draft, assessment_year: ay });
      setDraft(initialDraft(head));
      await load();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await head.client.remove(id);
      await load();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Card title={head.title}>
      <p className="-mt-2 mb-4 text-xs text-slate-400">{head.blurb}</p>

      {rows.length === 0 ? (
        <Empty>Nothing recorded yet.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                {head.columns.map((c) => (
                  <th key={c.key} className={`pb-2 ${c.money ? "text-right" : ""}`}>
                    {c.label}
                  </th>
                ))}
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.id)} className="border-b border-slate-100">
                  {head.columns.map((c) => (
                    <td
                      key={c.key}
                      className={`py-2 ${
                        c.money ? "text-right tabular-nums" : "capitalize"
                      }`}
                    >
                      {c.money ? inr(String(row[c.key])) : String(row[c.key])}
                    </td>
                  ))}
                  <td className="py-2 text-right">
                    <Button variant="danger" onClick={() => remove(String(row.id))}>
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
        {head.fields.map((f) => (
          <div key={f.key} className="w-40">
            {f.kind === "money" ? (
              <Field label={f.label} small>
                <NumInput
                  value={Number(draft[f.key] ?? 0)}
                  onChange={(v) => setDraft((d) => ({ ...d, [f.key]: v }))}
                />
              </Field>
            ) : f.kind === "select" ? (
              <Field label={f.label} small>
                <Select
                  value={String(draft[f.key] ?? f.options[0])}
                  onChange={(v) => setDraft((d) => ({ ...d, [f.key]: v }))}
                  options={f.options.map((o) => ({ value: o, label: o }))}
                />
              </Field>
            ) : (
              <label className="flex items-center gap-2 pb-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={Boolean(draft[f.key])}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, [f.key]: e.target.checked }))
                  }
                />
                {f.label}
              </label>
            )}
          </div>
        ))}
        <Button onClick={add} disabled={busy}>
          {busy ? "Adding…" : "Add"}
        </Button>
      </div>

      {error && (
        <div className="mt-3">
          <Alert>{error}</Alert>
        </div>
      )}
    </Card>
  );
}
