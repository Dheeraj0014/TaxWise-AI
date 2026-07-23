import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Card, Disclaimer, Empty } from "../../components/ui";
import { api, inr, type IdeaKind, type StoredRecommendation } from "../../lib/api";

const STATUS_STYLES: Record<StoredRecommendation["status"], string> = {
  suggested: "bg-slate-100 text-slate-600",
  accepted: "bg-emerald-100 text-emerald-700",
  dismissed: "bg-slate-100 text-slate-400",
};

/** Rendered in this order — cheapest for you first, donations last. */
const KIND_GROUPS: { kind: IdeaKind; heading: string; blurb: string }[] = [
  {
    kind: "expense",
    heading: "Already spending — just claim it",
    blurb:
      "Relief on money that has left your account anyway: premiums, loan interest, rent. Costs you nothing extra.",
  },
  {
    kind: "structural",
    heading: "Restructure — no new money needed",
    blurb:
      "Changes to how income and holdings are arranged, rather than fresh spending.",
  },
  {
    kind: "invest",
    heading: "Invest — the money stays yours",
    blurb:
      "You part with liquidity, not wealth: the amount becomes an asset you still own, subject to lock-in.",
  },
  {
    kind: "donate",
    heading: "Give — relief is a discount, not a gain",
    blurb:
      "Donations reduce tax but leave you with less overall. Worth doing because you want to give, never as a way to come out ahead.",
  },
];

export function RecommendationsPage({ ay }: { ay: number }) {
  const [recs, setRecs] = useState<StoredRecommendation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setRecs(await api.listRecommendations());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      await api.generateRecommendations(ay);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(id: string, status: StoredRecommendation["status"]) {
    setError(null);
    try {
      await api.patchRecommendation(id, status);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const open = recs.filter((r) => r.status !== "dismissed");
  const dismissed = recs.filter((r) => r.status === "dismissed");
  const outstanding = open.filter((r) => r.status === "suggested");
  // Donations are deliberately kept out of the headline figure: giving ₹1L to
  // save ₹31k is not ₹31k of "opportunity", it is ₹69k of net outflow.
  const potential = outstanding
    .filter((r) => r.kind !== "donate")
    .reduce((sum, r) => sum + Number(r.estimated_saving), 0);

  return (
    <div className="space-y-6">
      <Card
        title="Tax-saving strategies"
        actions={
          <Button onClick={generate} disabled={busy}>
            {busy ? "Analysing…" : "Regenerate"}
          </Button>
        }
      >
        <p className="-mt-2 text-xs text-slate-400">
          Generated from your stored finances for AY {ay}-{String(ay + 1).slice(2)}.
          Each saving is quantified by re-running the tax engine with the change
          applied — never estimated. Regenerating refreshes open suggestions but
          keeps whatever you have already accepted or dismissed.
        </p>

        {potential > 0 && (
          <p className="mt-4 text-sm text-slate-600">
            Outstanding opportunity:{" "}
            <span className="font-semibold text-emerald-600">{inr(potential)}</span>
            <span className="text-xs text-slate-400"> — excludes donations</span>
          </p>
        )}

        {error && (
          <div className="mt-4">
            <Alert>{error}</Alert>
          </div>
        )}

        <div className="mt-4 space-y-3">
          {loaded && open.length === 0 && !error && (
            <Empty>
              No strategies yet. Add your income and investments under{" "}
              <a href="#/finances" className="text-brand-600 hover:underline">
                My finances
              </a>
              , then regenerate.
            </Empty>
          )}

          {KIND_GROUPS.map(({ kind, heading, blurb }) => {
            const rows = open.filter((r) => r.kind === kind);
            if (rows.length === 0) return null;
            return (
              <section key={kind} className="pt-2">
                <h3 className="text-sm font-semibold text-slate-700">{heading}</h3>
                <p className="mb-2 mt-0.5 text-xs text-slate-400">{blurb}</p>
                <div className="space-y-3">
                  {rows.map((r) => (
                    <RecRow key={r.id} rec={r} onStatus={setStatus} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </Card>

      {dismissed.length > 0 && (
        <Card title="Dismissed">
          <div className="space-y-3">
            {dismissed.map((r) => (
              <RecRow key={r.id} rec={r} onStatus={setStatus} />
            ))}
          </div>
        </Card>
      )}

      <Disclaimer />
    </div>
  );
}

function RecRow({
  rec,
  onStatus,
}: {
  rec: StoredRecommendation;
  onStatus: (id: string, s: StoredRecommendation["status"]) => void;
}) {
  const muted = rec.status === "dismissed";
  const netCost = Number(rec.net_cost ?? 0);
  const amount = Number(rec.amount_modelled ?? 0);
  return (
    <div
      className={`flex flex-wrap items-start justify-between gap-3 rounded-lg p-3 ${
        muted ? "bg-slate-50/60" : "bg-slate-50"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className={`font-medium ${muted ? "text-slate-400" : "text-slate-800"}`}>
            {rec.title}
          </p>
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
              STATUS_STYLES[rec.status]
            }`}
          >
            {rec.status}
          </span>
        </div>
        {rec.note && <p className="mt-0.5 text-xs text-slate-500">{rec.note}</p>}
        {netCost > 0 ? (
          <p className="mt-1 text-xs text-amber-700">
            Costs {inr(amount)} to save {inr(rec.estimated_saving)} — you end up{" "}
            <span className="font-semibold">{inr(netCost)} poorer</span>. Do this to
            give, not to gain.
          </p>
        ) : (
          amount > 0 && (
            <p className="mt-1 text-xs text-slate-400">
              Modelled on {inr(amount)}
              {rec.kind === "invest" && " — which you still own afterwards"}
            </p>
          )
        )}
        {rec.required_documents.length > 0 && (
          <p className="mt-0.5 text-xs text-slate-400">
            Documents: {rec.required_documents.join(", ")}
          </p>
        )}
        {rec.deadline && (
          <p className="mt-0.5 text-xs text-amber-600">Deadline: {rec.deadline}</p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span
          className={`whitespace-nowrap rounded-md px-2 py-1 text-sm font-semibold ${
            muted ? "bg-slate-100 text-slate-400" : "bg-emerald-100 text-emerald-700"
          }`}
        >
          {inr(rec.estimated_saving)}
        </span>
        {rec.status !== "accepted" && (
          <Button variant="ghost" onClick={() => onStatus(rec.id, "accepted")}>
            Accept
          </Button>
        )}
        {rec.status !== "dismissed" ? (
          <Button variant="danger" onClick={() => onStatus(rec.id, "dismissed")}>
            Dismiss
          </Button>
        ) : (
          <Button variant="ghost" onClick={() => onStatus(rec.id, "suggested")}>
            Restore
          </Button>
        )}
      </div>
    </div>
  );
}
