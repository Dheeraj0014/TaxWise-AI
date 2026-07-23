// Session state (§9.2 store/). Context rather than Redux/Zustand: the app has
// exactly one piece of global state — who is signed in.
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "../lib/api";
import { getToken, onTokenChange, setToken } from "../lib/auth";

interface Session {
  token: string | null;
  email: string | null;
  signedIn: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const Ctx = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(getToken());
  const [email, setEmail] = useState<string | null>(null);

  // api.request clears the token on a 401/403, so the gate reacts to an
  // expired session without every caller having to handle it.
  useEffect(() => onTokenChange(setTok), []);

  useEffect(() => {
    if (!token) {
      setEmail(null);
      return;
    }
    api
      .me()
      .then((u) => setEmail(u.email))
      .catch(() => setToken(null));
  }, [token]);

  const value = useMemo<Session>(
    () => ({
      token,
      email,
      signedIn: Boolean(token),
      signIn: async (e, p) => {
        await api.login(e, p);
      },
      signUp: async (e, p) => {
        await api.register(e, p);
        await api.login(e, p);
      },
      signOut: () => api.logout(),
    }),
    [token, email],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
