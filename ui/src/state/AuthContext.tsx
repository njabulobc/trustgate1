import { createContext, useContext, useMemo, useState } from 'react';

import { api, SessionUser, setAuthToken } from '../api/client';

type AuthContextValue = {
  user: SessionUser | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [token, setToken] = useState<string | null>(null);

  async function login(username: string, password: string) {
    const response = await api.login(username, password);
    setToken(response.access_token);
    setUser(response.user);
    setAuthToken(response.access_token);
  }

  function logout() {
    setToken(null);
    setUser(null);
    setAuthToken(null);
  }

  const value = useMemo(() => ({ user, token, login, logout }), [user, token]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used in AuthProvider');
  return ctx;
}
