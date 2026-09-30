// Keep the standalone widget's onboarding flow synchronized with the React app.
import fs from "node:fs";
import { transform } from "esbuild";
import { parse } from "@babel/parser";
import postcss from "postcss";

const destination = new URL("../ezextend/react-design.jsx", import.meta.url);
let widget = fs.readFileSync(destination, "utf8");
async function inline(relative, adjust = code => code) {
  const source = adjust(fs.readFileSync(new URL("../src/" + relative, import.meta.url), "utf8"));
  let { code } = await transform(source, { loader: "tsx", jsx: "preserve", target: "es2022" });
  const ast = parse(code, { sourceType: "module", plugins: ["jsx"] });
  for (const node of [...ast.program.body].reverse()) {
    if (node.type === "ImportDeclaration" || node.type === "ExportNamedDeclaration") {
      code = code.slice(0, node.start) + (node.declaration ? code.slice(node.declaration.start, node.declaration.end) : "") + code.slice(node.end);
    }
  }
  return code;
}
const prelude = `
async function apiRequest(path, init = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), settings.requestTimeoutMs);
  try {
    if (settings.onboardingRequest) return await settings.onboardingRequest(path, { ...init, signal: controller.signal });
    const response = await fetch(settings.apiBaseUrl.replace(/\\/$/, "") + path, {
      ...init, signal: controller.signal,
      headers: { Accept: "application/json", ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...init.headers }
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(data?.error?.message || "Request failed. Please try again.", response.status);
    return data;
  } catch (error) {
    if (controller.signal.aborted) throw new ApiError("The request timed out. Resume your application to continue.");
    throw error;
  } finally { clearTimeout(timer); }
}
function useMutation({ mutationFn }) {
  const [state, setState] = useState({ data: null, error: null, isPending: false, isSuccess: false });
  const pending = useRef(false);
  async function mutate(payload) {
    if (pending.current) return;
    pending.current = true;
    setState(previous => ({ ...previous, error: null, isPending: true }));
    try {
      const data = await mutationFn(payload);
      setState({ data, error: null, isPending: false, isSuccess: true });
    } catch (error) { setState({ data: null, error, isPending: false, isSuccess: false }); }
    finally { pending.current = false; }
  }
  return { ...state, mutate };
}
`;
const generated = [
  prelude,
  await inline("features/onboarding/api.ts"),
  await inline("features/onboarding/DocumentFields.tsx"),
  await inline("features/onboarding/ApplicationPage.tsx", code => code.replace(
    "window.location.hash.slice(1)",
    '(window.location.hash || new URL(settings.initialPath, "https://tcg-widget.local").hash).slice(1)'
  )),
  await inline("features/portal/JoinPage.tsx", code => code.replace(
    'useQuery({ queryKey: ["registration-options"], queryFn: getRegistrationOptions, retry: 1 })',
    "useRegistrationOptions()"
  )),
].join("\n");
const begin = "    // BEGIN GENERATED ONBOARDING";
const end = "    // END GENERATED ONBOARDING";
if (widget.includes(begin)) {
  widget = widget.slice(0, widget.indexOf(begin)) + begin + "\n" + generated + end + widget.slice(widget.indexOf(end) + end.length);
} else {
  const start = widget.indexOf("    function JoinPage()");
  const finish = widget.indexOf("    const links =", start);
  if (start < 0 || finish < 0) throw new Error("Cannot locate widget registration component");
  widget = widget.slice(0, start) + begin + "\n" + generated + end + "\n\n" + widget.slice(finish);
}
widget = widget.replace('"/partner-stories", "/register"]', '"/partner-stories", "/register", "/onboarding"]');
widget = widget.replace('"/partner-stories": StoriesPage };', '"/partner-stories": StoriesPage, "/onboarding": ApplicationPage };');
widget = widget.replace("submitApplication: async (payload, { signal }) => savedPartner", "onboardingRequest: async (path, init) => responseJson");
const css = postcss.parse(fs.readFileSync(new URL("../src/features/onboarding/onboarding.css", import.meta.url), "utf8"));
css.walkRules(rule => {
  rule.selector = rule.selector.split(",").map(selector =>
    selector.trim().startsWith(".portal") ? selector.trim().replace(".portal", "[data-tcg-portal]") : "[data-tcg-portal] " + selector.trim()
  ).join(",");
});
const cssBegin = "/* BEGIN ONBOARDING STYLES */";
const cssEnd = "/* END ONBOARDING STYLES */";
const cssContent = cssBegin + "\n" + css.toString() + "\n" + cssEnd;
if (widget.includes(cssBegin)) {
  widget = widget.slice(0, widget.indexOf(cssBegin)) + cssContent + widget.slice(widget.indexOf(cssEnd) + cssEnd.length);
} else {
  const start = widget.indexOf("const PORTAL_STYLES = ") + "const PORTAL_STYLES = ".length;
  const close = widget.indexOf(String.fromCharCode(96), start + 1);
  widget = widget.slice(0, close) + "\n" + cssContent + "\n" + widget.slice(close);
}
parse(widget, { sourceType: "script", plugins: ["jsx"] });
fs.writeFileSync(destination, widget);
console.log("Standalone onboarding components and styles synchronized.");
