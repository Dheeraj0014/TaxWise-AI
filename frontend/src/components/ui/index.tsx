// Tailwind design-system primitives (§9.2 components/ui).
import type { ReactNode } from "react";

export function Card({
  title,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white p-5 ${className}`}
    >
      {(title || actions) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {typeof title === "string" ? (
            <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
          ) : (
            title
          )}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Field({
  label,
  children,
  small,
  hint,
}: {
  label: string;
  children: ReactNode;
  small?: boolean;
  hint?: string;
}) {
  return (
    <label className="block">
      <span
        className={`mb-1 block ${
          small ? "text-xs text-slate-500" : "text-sm font-medium text-slate-700"
        }`}
      >
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

export function NumInput({
  value,
  onChange,
  min = 0,
  step,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  step?: number;
}) {
  return (
    <input
      type="number"
      className="input"
      value={value}
      min={min}
      step={step}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  );
}

export function Select<T extends string | number>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <select
      className="input"
      value={value}
      onChange={(e) => {
        const raw = e.target.value;
        const match = options.find((o) => String(o.value) === raw);
        if (match) onChange(match.value);
      }}
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
  className?: string;
}) {
  const styles = {
    primary: "bg-brand-600 text-white hover:bg-brand-700",
    ghost: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "text-rose-600 hover:bg-rose-50",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg px-3 py-2 text-sm font-medium transition disabled:opacity-50 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export function Stat({
  label,
  value,
  tone = "neutral",
  sub,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "bad";
  sub?: string;
}) {
  const color = {
    neutral: "text-slate-900",
    good: "text-emerald-600",
    bad: "text-rose-600",
  }[tone];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
      {children}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
      {children}
    </div>
  );
}

export function Disclaimer() {
  return (
    <p className="text-xs leading-relaxed text-slate-400">
      Informational only, not tax or financial advice. Tax rules change with every
      Union Budget — verify against the current Finance Act and consult a qualified
      professional before filing.
    </p>
  );
}

/** Horizontal proportion bar, used for income/deduction composition. */
export function Bar({
  items,
}: {
  items: { label: string; value: number; color: string }[];
}) {
  const total = items.reduce((s, i) => s + i.value, 0);
  if (total <= 0) return null;
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100">
        {items.map((i) => (
          <div
            key={i.label}
            className={i.color}
            style={{ width: `${(i.value / total) * 100}%` }}
            title={`${i.label}: ${Math.round((i.value / total) * 100)}%`}
          />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        {items.map((i) => (
          <li key={i.label} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${i.color}`} />
            <span className="capitalize">{i.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
