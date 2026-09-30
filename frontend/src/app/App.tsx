import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { getReadiness } from "../api/client";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { AppLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { DealsPage } from "../pages/DealsPage";
import { DocumentsPage } from "../pages/DocumentsPage";
import { CommercialModelPage } from "../pages/CommercialModelPage";
import { CommercialPage } from "../pages/CommercialPage";
import { FoundationPage } from "../pages/FoundationPage";
import { LoginPage } from "../pages/LoginPage";
import { PartnerDetailPage } from "../pages/PartnerDetailPage";
import { PartnerUsersPage } from "../pages/PartnerUsersPage";
import { PartnersPage } from "../pages/PartnersPage";
import { PricingPage } from "../pages/PricingPage";
import { ProductsPage } from "../pages/ProductsPage";
import { RegisterPage } from "../pages/RegisterPage";

import { PublicLayout } from "../features/portal/PublicLayout";
import { HomePage, PartnershipPage, LevelsPage, StoriesPage } from "../features/portal/PortalPages";
import { JoinPage } from "../features/portal/JoinPage";
import "../features/portal/portal.css";

function AppShell() {
  const location = useLocation();
  const readiness = useQuery({
    queryKey: ["readiness"],
    queryFn: getReadiness,
    retry: 1,
    refetchInterval: 30_000,
    enabled: location.pathname === "/system",
  });

  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<PublicLayout />}>
      <Route index element={<HomePage />} />
      <Route path="/partner-with-tcg" element={<PartnershipPage />} />
      <Route path="/partner-levels" element={<LevelsPage />} />
      <Route path="/partner-stories" element={<StoriesPage />} />
      <Route path="/register" element={<JoinPage />} />
    </Route>
    <Route element={<ProtectedRoute />}>
      <Route element={<AppLayout />}>

        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/partners" element={<PartnersPage />} />
        <Route path="/partners/new" element={<RegisterPage admin />} />
        <Route path="/partners/:partnerId" element={<PartnerDetailPage />} />
        <Route path="/partners/:partnerId/users" element={<PartnerUsersPage />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/deals" element={<DealsPage />} />
        <Route path="/commercial-model" element={<CommercialModelPage />} />
        <Route path="/commercial" element={<CommercialPage />} />
        <Route path="/system" element={<FoundationPage query={readiness} />} />
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}

export default AppShell;
