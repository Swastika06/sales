import { apiRequest } from "../../api/client";

export const documentKinds = [
  ["COMPANY_LICENSE", "Company license"],
  ["PAN", "PAN"],
  ["GSTIN", "GSTIN"],
] as const;
export type DocumentKind = typeof documentKinds[number][0];
export type DocumentDrafts = Partial<Record<DocumentKind, { number: string; file?: File }>>;
export interface Application {
  id: string; partner_id: string; company_name: string; email: string; status: string;
  revision: number; assigned_to_id: string | null; review_comment: string | null;
  capabilities: string[]; required_documents: DocumentKind[]; mail_status: string | null; mail_error?: string | null;
  documents: { id: string; kind: DocumentKind; number: string; filename: string; size: number; revision: number; scan_status: string }[];
}
export interface ApplicationSession { token: string; application: Application }
export function onboardingRequest<T>(path: string, token?: string, body?: unknown, method?: string) {
  return apiRequest<T>("/onboarding" + path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers: token ? { "X-Application-Token": token } : {},
    ...(body !== undefined ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {}),
  });
}
export const requiresDocuments = (codes: string[]) => codes.some(code => code === "RESELLER" || code === "REFERRAL");
export async function saveDocuments(token: string, documents: DocumentDrafts) {
  for (const [kind, draft] of Object.entries(documents)) {
    if (!draft.file) continue;
    const body = new FormData();
    body.append("kind", kind); body.append("number", draft.number); body.append("file", draft.file);
    await onboardingRequest<Application>("/me/documents", token, body);
  }
}
export async function submitOnboarding(payload: unknown, documents: DocumentDrafts, existing: ApplicationSession | null, remember: (session: ApplicationSession) => void) {
  const session = existing ?? await onboardingRequest<ApplicationSession>("/applications", undefined, payload);
  remember(session);
  const current = await onboardingRequest<Application>("/me", session.token);
  if (!["DRAFT", "CHANGES_REQUESTED"].includes(current.status)) return current;
  await saveDocuments(session.token, documents);
  return onboardingRequest<Application>("/me/submit", session.token, {});
}
