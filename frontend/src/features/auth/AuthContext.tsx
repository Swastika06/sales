import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useMemo, useSyncExternalStore } from "react";

import { getCurrentUser, login as requestLogin, type CurrentUser } from "../../api/client";
import { clearAccessToken, getAccessToken, saveAccessToken, subscribeSession } from "./session";

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
  const subscribe = useCallback((listener: () => void) => subscribeSession(() => {
    queryClient.clear();
    listener();
  }), [queryClient]);
  const token = useSyncExternalStore(subscribe, getAccessToken, () => null);
  const userQuery = useQuery({
    queryKey: ["current-user", token],
    queryFn: () => getCurrentUser(),
    enabled: Boolean(token),
    retry: false,
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      user: token ? userQuery.data ?? null : null,
      isLoading: Boolean(token) && userQuery.isLoading,
      isAuthenticated: Boolean(token && userQuery.data),
      login: async (email: string, password: string) => {
        const accessToken = await requestLogin(email, password);
        // Verify the user before considering sign-in complete or saving the session.
        const user = await getCurrentUser(accessToken);
        queryClient.clear();
        saveAccessToken(accessToken);
        queryClient.setQueryData(["current-user", accessToken], user);
      },
      logout: () => {
        clearAccessToken();
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
