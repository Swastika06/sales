// The standalone build supplies this configuration from EzComponent's settings.
export const apiConfig = {
  apiBaseUrl: ((import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ?? "") + "/api/v1",
  tokenStorageKey: "partner_portal_token",
  requestTimeoutMs: 15_000,
};
