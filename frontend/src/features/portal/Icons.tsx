import type { CSSProperties } from "react";

const paths: Record<string, string> = {
  arrow: "M4 12h15m-6-6 6 6-6 6",
  diagonal: "M6 18 18 6M6 6h12v12",
  chevron: "m6 9 6 6 6-6",
  check: "m5 12 4 4L19 6",
  plus: "M12 5v14M5 12h14",
  close: "m6 6 12 12M6 18 18 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  globe: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z",
  growth: "M4 20V10m6 10V6m6 14V3M3 6l6-3 5 1 6-3m-4 0h4v4",
  layers: "m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5",
  network: "M8 6h8M6 8v8m2 2h8m2-10v8M8 8l8 8M8 16l8-8M8 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm12 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm12 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z",
  spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z",
  people: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM2 21v-3a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v3m0-17a4 4 0 0 1 0 8m3 3a5 5 0 0 1 3 4v2",
  book: "M12 5v16M12 5C8 2 4 3 2 4v15c4-2 7-1 10 2 3-3 6-4 10-2V4c-2-1-6-2-10 1Z",
  shield: "m12 2 9 4v6c0 5-6 8-9 10-3-2-9-5-9-10V6l9-4Zm-4 10 3 3 5-6",
  briefcase: "M8 6V3h8v3M3 6h18v14H3V6Zm0 5c5 4 13 4 18 0M10 12h4v4h-4v-4Z",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18",
  mail: "M3 5h18v14H3V5Zm0 1 9 7 9-7",
  lock: "M6 10h12v11H6V10Zm2 0V6a4 4 0 0 1 8 0v4M12 14v3",
};
export function Icon({ name = "arrow", size = 20, style }: { name?: string; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name] ?? paths.arrow} /></svg>;
}
export function TcgMark() {
  return <svg className="tcg-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M7 30V10h25M14 30V17h18M21 30V24h11" stroke="currentColor" strokeWidth="4.5" /></svg>;
}

