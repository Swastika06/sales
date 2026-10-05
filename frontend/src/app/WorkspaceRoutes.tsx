import { Route } from "react-router-dom";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { AppLayout } from "../layouts/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { DealsPage } from "../pages/DealsPage";
import { DocumentsPage } from "../pages/DocumentsPage";
import { CommercialModelPage } from "../pages/CommercialModelPage";
import { CommercialPage } from "../pages/CommercialPage";
import { SystemStatusPage } from "../pages/SystemStatusPage";
import { PartnerDetailPage } from "../pages/PartnerDetailPage";
import { PartnerUsersPage } from "../pages/PartnerUsersPage";
import { PartnersPage } from "../pages/PartnersPage";
import { PricingPage } from "../pages/PricingPage";
import { ProductsPage } from "../pages/ProductsPage";
import { RegisterPage } from "../pages/RegisterPage";
import { StaffUsersPage } from "../pages/StaffUsersPage";
import { OnboardingReviewPage } from "../pages/OnboardingReviewPage";

// Return route elements so the local app and the embedded widget use the same tree.
export function workspaceRoutes(embedded = false) {
  return <Route element={<ProtectedRoute />}>
    <Route element={<AppLayout embedded={embedded} />}>
      <Route path="/staff-users" element={<StaffUsersPage />} />
      <Route path="/onboarding-review" element={<OnboardingReviewPage />} />
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
      <Route path="/system" element={<SystemStatusPage />} />
    </Route>
  </Route>;
}
