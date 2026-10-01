import { Navigate, Route, Routes } from "react-router-dom";
import { workspaceRoutes } from "./WorkspaceRoutes";
import { LoginPage } from "../pages/LoginPage";
import { PublicLayout } from "../features/portal/PublicLayout";
import { HomePage, PartnershipPage, LevelsPage, StoriesPage } from "../features/portal/PortalPages";
import { ApplicationPage } from "../features/onboarding/ApplicationPage";
import { JoinPage } from "../features/portal/JoinPage";
import "../features/onboarding/onboarding.css";
import "../features/portal/portal.css";

export default function AppShell() {
  return <Routes>
    <Route element={<PublicLayout />}>
      <Route index element={<HomePage />} />
      <Route path="/partner-with-tcg" element={<PartnershipPage />} />
      <Route path="/partner-levels" element={<LevelsPage />} />
      <Route path="/partner-stories" element={<StoriesPage />} />
      <Route path="/register" element={<JoinPage />} />
      <Route path="/onboarding" element={<ApplicationPage />} />
      <Route path="/login" element={<LoginPage />} />
    </Route>
    {workspaceRoutes()}
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}
