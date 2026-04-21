import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  login, logout, exchangeCode, refreshTokens,
  loadTokens, clearTokens, isTokenValid, getEmail,
  type Tokens,
} from "./auth";

interface AuthState {
  tokens: Tokens | null;
  email: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  signIn: () => void;
  signOut: () => void;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ tokens: null, email: null, loading: true });

  const setTokens = useCallback((tokens: Tokens | null) => {
    setState({
      tokens,
      email: tokens ? getEmail(tokens.idToken) : null,
      loading: false,
    });
  }, []);

  // On mount: handle callback or restore session
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (code && state) {
      // Remove code/state from URL without reload
      window.history.replaceState({}, "", window.location.pathname);
      exchangeCode(code, state)
        .then(setTokens)
        .catch(() => { clearTokens(); setState(s => ({ ...s, loading: false })); });
      return;
    }

    const stored = loadTokens();
    if (!stored) { setState(s => ({ ...s, loading: false })); return; }

    if (isTokenValid(stored)) {
      setTokens(stored);
    } else {
      refreshTokens().then(t => setTokens(t ?? null));
    }
  }, [setTokens]);

  // Proactive token refresh (5 min before expiry)
  useEffect(() => {
    if (!state.tokens) return;
    const ms = state.tokens.expiresAt - Date.now() - 5 * 60 * 1000;
    if (ms <= 0) return;
    const id = setTimeout(() => {
      refreshTokens().then(t => { if (t) setTokens(t); });
    }, ms);
    return () => clearTimeout(id);
  }, [state.tokens, setTokens]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!state.tokens) return null;
    if (isTokenValid(state.tokens)) return state.tokens.accessToken;
    const refreshed = await refreshTokens();
    if (refreshed) { setTokens(refreshed); return refreshed.accessToken; }
    setTokens(null);
    return null;
  }, [state.tokens, setTokens]);

  return (
    <AuthContext.Provider value={{
      ...state,
      signIn: login,
      signOut: logout,
      getAccessToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
