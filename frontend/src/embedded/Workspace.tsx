import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, MemoryRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { workspaceRoutes } from "../app/WorkspaceRoutes";
import { AuthProvider } from "../features/auth/AuthContext";
import { LoginPage } from "../pages/LoginPage";

interface WorkspaceProps {
  initialPath: string;
  onExit: (path: string) => void;
}

function PublicPage({ onExit }: Pick<WorkspaceProps, "onExit">) {
  const location = useLocation();
  useEffect(() => {
    onExit(location.pathname + location.search + location.hash);
  }, [location.pathname, location.search, location.hash, onExit]);
  return null;
}

function WorkspaceContent({ onExit }: Pick<WorkspaceProps, "onExit">) {
  const location = useLocation();
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const heading = root.current?.querySelector<HTMLElement>("h1");
    if (heading) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
  }, [location.pathname]);
  return <div ref={root}>
    <div className="embedded-workspace-toolbar"><Link to="/">Back to Partner Network</Link></div>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {workspaceRoutes()}
      <Route path="/" element={<PublicPage onExit={onExit} />} />
      <Route path="/register" element={<PublicPage onExit={onExit} />} />
      <Route path="/onboarding" element={<PublicPage onExit={onExit} />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  </div>;
}

export function EmbeddedWorkspace({ initialPath, onExit }: WorkspaceProps) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 15_000, retry: 1 } },
  }));
  useEffect(() => () => { queryClient.clear(); }, [queryClient]);
  return <div data-tcg-workspace="">
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <WorkspaceContent onExit={onExit} />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  </div>;
}
