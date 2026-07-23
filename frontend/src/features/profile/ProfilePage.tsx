import { useEffect, useState } from "react";

import { Alert, Button, Card, Field, Select } from "../../components/ui";
import { api, type Profile } from "../../lib/api";

export function ProfilePage({
  years,
  onSaved,
}: {
  years: number[];
  onSaved?: () => void;
}) {
  const [form, setForm] = useState({
    full_name: "",
    pan: "",
    age: 30,
    residential_status: "resident",
    preferred_regime: "",
    assessment_year: years[0] ?? 2026,
    locale: "en",
  });
  const [masked, setMasked] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((p: Profile) => {
        setMasked(p.pan_masked);
        setForm((f) => ({
          ...f,
          full_name: p.full_name ?? "",
          age: p.age ?? 30,
          residential_status: p.residential_status,
          preferred_regime: p.preferred_regime ?? "",
          assessment_year: p.assessment_year,
          locale: p.locale,
        }));
      })
      // 404 simply means "not filled in yet" — the form starts empty.
      .catch(() => {});
  }, []);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const p = await api.updateProfile({
        ...form,
        preferred_regime: form.preferred_regime || undefined,
        // Only send PAN when the user typed a new one; the API returns it masked.
        pan: form.pan || undefined,
      });
      setMasked(p.pan_masked);
      setForm((f) => ({ ...f, pan: "" }));
      setSaved(true);
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Taxpayer profile" className="max-w-2xl">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name">
          <input
            className="input"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </Field>

        <Field
          label="PAN"
          hint={masked ? `Currently stored as ${masked}` : "Stored masked."}
        >
          <input
            className="input"
            placeholder={masked ? "Enter to replace" : "ABCDE1234F"}
            value={form.pan}
            onChange={(e) =>
              setForm({ ...form, pan: e.target.value.toUpperCase() })
            }
          />
        </Field>

        <Field label="Age">
          <input
            type="number"
            className="input"
            min={0}
            max={120}
            value={form.age}
            onChange={(e) => setForm({ ...form, age: Number(e.target.value) })}
          />
        </Field>

        <Field label="Residential status">
          <Select
            value={form.residential_status}
            onChange={(v) => setForm({ ...form, residential_status: v })}
            options={[
              { value: "resident", label: "Resident" },
              { value: "nri", label: "Non-resident" },
              { value: "rnor", label: "Resident but not ordinarily resident" },
            ]}
          />
        </Field>

        <Field label="Default assessment year">
          <Select
            value={form.assessment_year}
            onChange={(v) => setForm({ ...form, assessment_year: v })}
            options={years.map((y) => ({
              value: y,
              label: `AY ${y}-${String(y + 1).slice(2)}`,
            }))}
          />
        </Field>

        <Field label="Preferred regime" hint="Leave blank to always compare.">
          <Select
            value={form.preferred_regime}
            onChange={(v) => setForm({ ...form, preferred_regime: v })}
            options={[
              { value: "", label: "No preference" },
              { value: "old", label: "Old" },
              { value: "new", label: "New" },
            ]}
          />
        </Field>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <Button onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save profile"}
        </Button>
        {saved && <span className="text-sm text-emerald-600">Saved.</span>}
      </div>

      {error && (
        <div className="mt-3">
          <Alert>{error}</Alert>
        </div>
      )}

      <p className="mt-4 text-xs text-slate-400">
        PAN is masked in every API response. Production deployments must add
        column-level envelope encryption with a KMS-managed key (§12) — this build
        stores it in plain text locally.
      </p>
    </Card>
  );
}
