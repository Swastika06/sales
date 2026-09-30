import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useMemo, useState } from "react";

import { getCurrentUser, login as requestLogin, type CurrentUser } from "../../api/client";

const TOKEN_KEY = "partner_portal_token";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const userQuery = useQuery({
    queryKey: ["current-user", token],
    queryFn: getCurrentUser,
    enabled: Boolean(token),
    retry: false,
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      user: userQuery.data ?? null,
      isLoading: Boolean(token) && userQuery.isLoading,
      isAuthenticated: Boolean(token && userQuery.data),
      login: async (email: string, password: string) => {
        const accessToken = await requestLogin(email, password);
        queryClient.clear();
        localStorage.setItem(TOKEN_KEY, accessToken);
        setToken(accessToken);
        await queryClient.invalidateQueries({ queryKey: ["current-user"] });
      },
      logout: () => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        queryClient.clear();
      },
    }),
    [queryClient, token, userQuery.data, userQuery.isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
