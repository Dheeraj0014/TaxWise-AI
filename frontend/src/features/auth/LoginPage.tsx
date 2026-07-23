import { useState } from "react";

import { Alert, Button, Card, Disclaimer, Field } from "../../components/ui";
import { useSession } from "../../store/session";

export function LoginPage() {
  const { signIn, signUp } = useSession();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const registering = mode === "register";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (registering) await signUp(email, password);
      else await signIn(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <header className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-slate-900">
          AI Tax Optimizer <span className="text-brand-600">India</span>
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Sign in to save your financial profile and track recommendations.
        </p>
      </header>

      <Card>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email">
            <input
              className="input"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field
            label="Password"
            hint={registering ? "At least 8 characters." : undefined}
          >
            <input
              className="input"
              type="password"
              required
              minLength={registering ? 8 : undefined}
              autoComplete={registering ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          {error && <Alert>{error}</Alert>}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Working…" : registering ? "Create account" : "Sign in"}
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          {registering ? "Already have an account?" : "No account yet?"}{" "}
          <button
            className="font-medium text-brand-600 hover:underline"
            onClick={() => {
              setMode(registering ? "login" : "register");
              setError(null);
            }}
          >
            {registering ? "Sign in" : "Create one"}
          </button>
        </p>
      </Card>

      <div className="mt-6 space-y-3">
        <p className="text-center text-xs text-slate-400">
          You can also use the calculator without an account.
        </p>
        <Disclaimer />
      </div>
    </div>
  );
}
