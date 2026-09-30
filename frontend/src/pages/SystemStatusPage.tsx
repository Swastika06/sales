import { useQuery } from "@tanstack/react-query";
import { getReadiness } from "../api/client";
import { FoundationPage } from "./FoundationPage";

export function SystemStatusPage() {
  const readiness = useQuery({
    queryKey: ["readiness"], queryFn: getReadiness, retry: 1, refetchInterval: 30_000,
  });
  return <FoundationPage query={readiness} />;
}
