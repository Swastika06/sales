/*
 * TCG Partner Network — standalone ezextend edition.
 * Synced with src/features/portal (public UI); React 18+ and host render() required.
 * No package imports, router dependency, external image assets, or persisted credentials.
 *
 * Configure BEFORE mounting, or pass <EzComponent config={...} />:
 * window.TCG_PARTNER_PORTAL_CONFIG = {
 *   apiBaseUrl: "/api/v1",             // Complete API prefix, including /api/v1.
 *   workspaceUrl: "/login",            // Existing authenticated portal sign-in.
 *   publicBaseUrl: "",                 // Public portal origin/base for new-tab links.
 *   initialPath: "/",                  // Supports /register?type=RESELLER.
 *   loadFonts: true,                    // false when the host already provides fonts.
 *   requestTimeoutMs: 15000,
 *   // Optional ezextend bridges instead of fetch (same JSON contracts as the API):
 *   // getRegistrationOptions: async ({ signal }) => ({ partner_types, countries }),
 *   // submitApplication: async (payload, { signal }) => savedPartner,
 * };
 * Navigation stays inside this widget; it does not overwrite the host's URL/history.
 * New-tab public links and workspace sign-in use the configured destination URLs.
 * Registration uses real responses only; there is no simulated success or demo data.
 */
function EzComponent({ config = {} } = {}) {
  const settings = React.useRef({
    apiBaseUrl: "/api/v1",
    workspaceUrl: "/login",
    publicBaseUrl: "",
    initialPath: "/",
    loadFonts: true,
    fontStylesheetUrl: "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap",
    requestTimeoutMs: 15000,
    ...(typeof window !== "undefined" ? window.TCG_PARTNER_PORTAL_CONFIG : {}),
    ...config,
  }).current;
  const rootRef = React.useRef(null);
  const instanceId = "tcg-ez-" + React.useId().replace(/[^a-zA-Z0-9_-]/g, "");

  // Define helper components once per mounted widget so input state survives re-renders.
  const Portal = React.useMemo(() => {
    const { useState, useEffect, useRef, useCallback, useContext } = React;
    const id = name => instanceId + "-" + name;
    const Navigation = React.createContext(null);
    const allowedPaths = new Set(["/", "/partner-with-tcg", "/partner-levels", "/partner-stories", "/register"]);

    function parseLocation(destination, sequence = 0) {
      const parsed = new URL(destination, "https://tcg-widget.local");
      return {
        pathname: allowedPaths.has(parsed.pathname) ? parsed.pathname : "/",
        search: parsed.search,
        hash: ["#benefits", "#solutions", "#levels"].includes(parsed.hash) ? parsed.hash : "",
        sequence,
      };
    }
    function useLocation() { return useContext(Navigation).location; }
    function useSearchParams() { return [new URLSearchParams(useLocation().search)]; }
    function Link({ to, children, onClick, target, ...props }) {
      const navigation = useContext(Navigation);
      const workspace = to === "/login";
      const href = workspace ? settings.workspaceUrl : settings.publicBaseUrl.replace(/\/$/, "") + to;
      return <a {...props} href={href} target={target} onClick={event => {
        onClick?.(event);
        if (event.defaultPrevented || workspace || target === "_blank" || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        navigation.navigate(to);
      }}>{children}</a>;
    }
    function NavLink({ to, className = "", ...props }) {
      const active = useLocation().pathname === to;
      return <Link {...props} to={to} className={[className, active ? "active" : ""].filter(Boolean).join(" ")} aria-current={active ? "page" : undefined} />;
    }

    class ApiError extends Error {
      constructor(message, status = 0) { super(message); this.name = "ApiError"; this.status = status; }
    }
    async function request(path, { payload, signal } = {}) {
      const controller = new AbortController();
      const relayAbort = () => controller.abort();
      if (signal?.aborted) controller.abort();
      signal?.addEventListener("abort", relayAbort, { once: true });
      let timedOut = false;
      const timer = setTimeout(() => { timedOut = true; controller.abort(); }, settings.requestTimeoutMs);
      let stopWaiting;
      try {
        const cancelled = new Promise((_, reject) => {
          stopWaiting = () => reject(new DOMException("Request cancelled", "AbortError"));
          if (controller.signal.aborted) stopWaiting();
          else controller.signal.addEventListener("abort", stopWaiting, { once: true });
        });
        const operation = (async () => {
          if (payload && settings.submitApplication) return settings.submitApplication(payload, { signal: controller.signal });
          if (!payload && settings.getRegistrationOptions) return settings.getRegistrationOptions({ signal: controller.signal });
          const response = await fetch(settings.apiBaseUrl.replace(/\/+$/, "") + path, {
            method: payload ? "POST" : "GET",
            headers: { Accept: "application/json", ...(payload ? { "Content-Type": "application/json" } : {}) },
            ...(payload ? { body: JSON.stringify(payload) } : {}),
            signal: controller.signal,
          });
          const data = await response.json().catch(() => null);
          if (!response.ok) throw new ApiError(data?.error?.message || "The request could not be completed. Please try again.", response.status);
          return data;
        })();
        return await Promise.race([operation, cancelled]);
      } catch (error) {
        if (timedOut) throw new ApiError("The request timed out. Please check your connection and try again.");
        if (controller.signal.aborted) throw error;
        if (error instanceof ApiError) throw error;
        throw new ApiError("We couldn’t reach TCG. Please try again. Your details are still here.");
      } finally {
        clearTimeout(timer);
        signal?.removeEventListener("abort", relayAbort);
        controller.signal.removeEventListener("abort", stopWaiting);
      }
    }
    function useRegistrationOptions() {
      const [state, setState] = useState({ data: null, isLoading: true, isFetching: true, isError: false });
      const current = useRef(null);
      const refetch = useCallback(async () => {
        current.current?.abort();
        const controller = new AbortController();
        current.current = controller;
        setState({ data: null, isLoading: true, isFetching: true, isError: false });
        try {
          const data = await request("/partners/registration-options", { signal: controller.signal });
          const supported = new Set(["REFERRAL", "RESELLER", "SYSTEM_INTEGRATOR"]);
          const partner_types = Array.isArray(data?.partner_types) ? data.partner_types.filter(item => item && supported.has(item.code) && typeof item.name === "string") : [];
          const countries = Array.isArray(data?.countries) ? data.countries.filter(item => item && /^[A-Z]{2}$/.test(item.code) && typeof item.name === "string") : [];
          if (!partner_types.length || !countries.length) throw new ApiError("Partnership options are unavailable.");
          if (!controller.signal.aborted) setState({ data: { partner_types, countries }, isLoading: false, isFetching: false, isError: false });
        } catch {
          if (!controller.signal.aborted) setState({ data: null, isLoading: false, isFetching: false, isError: true });
        }
      }, []);
      useEffect(() => { void refetch(); return () => current.current?.abort(); }, [refetch]);
      return { ...state, refetch };
    }
    function useApplicationSubmission() {
      const [state, setState] = useState({ data: null, error: null, isPending: false, isSuccess: false });
      const current = useRef(null);
      const pending = useRef(false);
      useEffect(() => () => current.current?.abort(), []);
      async function mutate(payload) {
        if (pending.current) return;
        pending.current = true;
        const controller = new AbortController();
        current.current = controller;
        setState({ data: null, error: null, isPending: true, isSuccess: false });
        try {
          const data = await request("/partners/register", { payload, signal: controller.signal });
          if (!data || typeof data.id !== "string" || !data.id.trim() || data.status !== "PENDING_APPROVAL") {
            throw new ApiError("We couldn’t verify the application response. Please contact TCG before submitting again.");
          }
          if (!controller.signal.aborted) setState({ data, error: null, isPending: false, isSuccess: true });
        } catch (error) {
          if (!controller.signal.aborted) setState({ data: null, error, isPending: false, isSuccess: false });
        } finally { pending.current = false; }
      }
      return { ...state, mutate, clearError: () => setState(previous => ({...previous, error: null})) };
    }

    const PORTAL_STYLES = `/* Embed-specific resets: no dependency on the workspace stylesheet. */
[data-tcg-portal]{width:100%;min-width:0;container-type:inline-size;container-name:tcg-portal;isolation:isolate;text-align:left;color-scheme:light;font-synthesis:none;text-rendering:optimizeLegibility}
[data-tcg-portal] :is(button,input,select){font-family:inherit}
[data-tcg-portal] button{border:0;cursor:pointer;padding:10px 16px;background:transparent;color:inherit}
[data-tcg-portal] button:disabled{cursor:not-allowed}
/* Public partner-network design system, scoped away from the workspace. */
[data-tcg-portal]{--p-ink:#192b38;--p-muted:#687078;--p-orange:#c64a24;--p-orange-hover:#b9411c;--p-cream:#f8f6f2;--p-line:#e4e3de;--p-navy:#142e3d;color:var(--p-ink);background:#fff;font-family:"DM Sans",Arial,sans-serif;font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
[data-tcg-portal] *{box-sizing:border-box}[data-tcg-portal] h1,[data-tcg-portal] h2,[data-tcg-portal] h3,[data-tcg-portal] h4{color:inherit;font-family:Manrope,"DM Sans",sans-serif}[data-tcg-portal] h1{max-width:none;font-size:clamp(44px,4.7vw,66px);font-weight:600;line-height:1.15;letter-spacing:-.055em;margin:0}[data-tcg-portal] h2{font-size:clamp(27px,2.55vw,36px);font-weight:600;line-height:1.25;letter-spacing:-.045em;margin:13px 0}[data-tcg-portal] h3{font-weight:600;letter-spacing:-.035em}[data-tcg-portal] p{color:var(--p-muted)}[data-tcg-portal] a{color:inherit;text-decoration:none}[data-tcg-portal] button{font:inherit;border-radius:0}[data-tcg-portal] button:disabled{cursor:not-allowed;opacity:.5}[data-tcg-portal] button,[data-tcg-portal] a{-webkit-tap-highlight-color:transparent}[data-tcg-portal] :is(button,a,input,select,summary,[tabindex]):focus-visible{outline:3px solid #dd773f;outline-offset:5px}[data-tcg-portal] svg{flex-shrink:0;vertical-align:middle}
[data-tcg-portal] .p-container{width:min(1240px,calc(100% - 112px));margin-inline:auto}[data-tcg-portal] .p-skip{position:fixed;left:20px;top:-100px;z-index:100;padding:12px 24px;color:#fff!important;background:var(--p-navy)}[data-tcg-portal] .p-skip:focus{top:12px}
[data-tcg-portal] .p-announcement{display:flex;align-items:center;justify-content:center;gap:24px;min-height:36px;padding:7px 20px;background:var(--p-navy);color:#dce1e3;font-size:11px;letter-spacing:.02em}[data-tcg-portal] .p-announcement a{display:flex;align-items:center;gap:9px;color:#fff}[data-tcg-portal] .p-announcement a:hover{text-decoration:underline}
[data-tcg-portal] .p-header{position:sticky;top:0;z-index:30;background:#fffffffa;border-bottom:1px solid var(--p-line);backdrop-filter:blur(16px)}[data-tcg-portal] .p-header-inner{display:flex;align-items:center;justify-content:space-between;min-height:87px;gap:28px}[data-tcg-portal] .p-brand{display:inline-flex;align-items:center;gap:8px;flex-shrink:0}[data-tcg-portal] .tcg-mark{width:35px;height:40px;color:var(--p-orange)}[data-tcg-portal] .p-wordmark{font-size:28px;font-weight:700;line-height:.9;letter-spacing:-.045em}[data-tcg-portal] .p-wordmark>span{display:block;font-size:13px;letter-spacing:.04em;font-weight:500;margin-top:7px}[data-tcg-portal] .p-brand-divider{width:1px;height:33px;background:#d9dcdd;margin:0 7px 0 14px}[data-tcg-portal] .p-brand-label{font-size:9px;line-height:1.6;letter-spacing:.12em;font-weight:600;color:#69737b}
[data-tcg-portal] .p-nav{display:flex;align-items:center;gap:29px}[data-tcg-portal] .p-nav>a{position:relative;font-size:12px;font-weight:500;white-space:nowrap;transition:color .2s}[data-tcg-portal] .p-nav>a:hover,[data-tcg-portal] .p-nav>a.active{color:var(--p-orange)}[data-tcg-portal] .p-nav>a.active::after{content:"";position:absolute;bottom:-33px;height:2px;background:var(--p-orange);left:0;right:0}[data-tcg-portal] .p-nav .p-login{display:flex;gap:7px;align-items:center;padding-left:18px;border-left:1px solid var(--p-line)}
[data-tcg-portal] .p-button{display:inline-flex;align-items:center;justify-content:center;gap:24px;padding:14px 22px;border-radius:5px;background:var(--p-orange);border:1px solid var(--p-orange);color:white;font-size:12px;line-height:1.6;font-weight:600;text-decoration:none;cursor:pointer;transition:background .2s,border-color .2s,transform .2s,box-shadow .2s}[data-tcg-portal] .p-button:hover{background:var(--p-orange-hover);border-color:var(--p-orange-hover);transform:translateY(-2px);box-shadow:0 5px 15px #a1432220}[data-tcg-portal] .p-button-outline{background:transparent;color:var(--p-ink);border-color:#cdd0cf}[data-tcg-portal] .p-button-outline:hover{border-color:var(--p-orange);background:#fcf4ed}[data-tcg-portal] .p-button-small{padding:10px 16px;gap:19px}[data-tcg-portal] .p-menu-toggle{display:none;color:var(--p-ink);background:transparent;padding:10px}
[data-tcg-portal] .p-eyebrow{display:inline-flex;align-items:center;gap:10px;color:#a64b2c;font-size:10px;font-weight:700;letter-spacing:.15em;line-height:1.5}[data-tcg-portal] .p-eyebrow-line{width:25px;height:2px;background:var(--p-orange)}
[data-tcg-portal] .p-hero{overflow:hidden;background:var(--p-cream)}[data-tcg-portal] .p-hero-grid{display:grid;grid-template-columns:1.08fr 1fr;align-items:center;min-height:582px;gap:12px}[data-tcg-portal] .p-hero-copy{padding:62px 0 60px;z-index:1}[data-tcg-portal] .p-hero-copy h1{margin:24px 0 25px;white-space:nowrap}[data-tcg-portal] em{font-family:Georgia,"Times New Roman",serif;color:var(--p-orange);font-weight:400;letter-spacing:-.05em}[data-tcg-portal] .p-hero-copy>p{font-size:15px;line-height:1.9;margin:0 0 28px}[data-tcg-portal] .p-hero-buttons{display:flex;align-items:center;gap:12px;flex-wrap:wrap}[data-tcg-portal] .p-hero-note{display:flex;align-items:center;gap:12px;margin-top:33px;color:#626d72;font-size:10px}[data-tcg-portal] .p-hero-note strong{color:#535d62;font-weight:500}[data-tcg-portal] .p-overlap-icons{display:flex;padding-right:3px}[data-tcg-portal] .p-overlap-icons>span{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#e8e6df;color:#737a72;border:2px solid var(--p-cream);margin-right:-4px}[data-tcg-portal] .p-overlap-icons>span:nth-child(2){background:#f0dfd2;color:#a46841}[data-tcg-portal] .p-overlap-icons>span:nth-child(3){background:#dce7e6;color:#536f6d}[data-tcg-portal] .p-hero-bottom{display:flex;justify-content:space-between;gap:20px;align-items:center;border-top:1px solid #e4e1da;padding-block:20px;color:#626d72;font-size:9px;letter-spacing:.14em}[data-tcg-portal] .p-hero-bottom a{display:flex;gap:14px;align-items:center;font-size:10px;letter-spacing:0}
[data-tcg-portal] .p-network-art{position:relative;width:100%;height:520px;isolation:isolate}[data-tcg-portal] .p-art-grid{position:absolute;inset:30px -20px;z-index:-2;background-image:linear-gradient(#a38c7214 1px,transparent 1px),linear-gradient(90deg,#a38c7214 1px,transparent 1px);background-size:43px 43px;mask-image:radial-gradient(ellipse at center,black 15%,transparent 66%)}[data-tcg-portal] .p-network-art::before{content:"";position:absolute;inset:35px;border-radius:50%;z-index:-1;background:radial-gradient(ellipse,#e5b18335,transparent 65%)}[data-tcg-portal] .p-globe-art{position:absolute;width:115%;height:115%;left:-8%;top:-5%}[data-tcg-portal] .p-art-orbit{position:absolute;border:1px solid #d0beb250;border-radius:50%;inset:13% 4%;transform:rotate(-30deg)}[data-tcg-portal] .p-art-orbit-two{inset:20% -8%;transform:rotate(38deg)}[data-tcg-portal] .p-art-tag{display:flex;align-items:center;gap:12px;position:absolute;background:#fffefaee;border:1px solid #fff;border-radius:8px;box-shadow:0 10px 30px #66554110;padding:13px 16px}[data-tcg-portal] .p-art-tag small{display:block;color:#8d8881;font-size:7px;letter-spacing:.08em;margin-bottom:4px}[data-tcg-portal] .p-art-tag strong{display:block;font-size:11px;font-weight:600}[data-tcg-portal] .p-art-tag-top{left:8%;top:48px;transform:rotate(-3deg);animation:tcg-ez-float 7s ease-in-out infinite}[data-tcg-portal] .p-art-tag .p-icon-tile{width:35px;height:35px;border-radius:5px}[data-tcg-portal] .p-live-dot{height:6px;width:6px;background:#74a489;border-radius:50%;margin-left:9px}[data-tcg-portal] .p-art-tag-left{left:-2%;top:58%;padding:12px 15px;font-size:10px;transform:rotate(-5deg)}[data-tcg-portal] .p-art-tag-left>svg{color:var(--p-orange)}[data-tcg-portal] .p-art-tag-right{right:-1%;bottom:59px;transform:rotate(3deg);animation:tcg-ez-float 8s ease-in-out infinite reverse}[data-tcg-portal] .p-art-arrow{display:grid;place-items:center;width:35px;height:35px;color:#628170;background:#eaf0e8;border-radius:6px}[data-tcg-portal] .p-art-coordinate{position:absolute;bottom:4px;left:20%;font-family:monospace;color:#928e84;font-size:7px;letter-spacing:.1em}[data-tcg-portal] .p-art-plus{position:absolute;color:#ad7f55;font-weight:300;font-size:18px}[data-tcg-portal] .p-art-plus-a{top:32%;right:5%}[data-tcg-portal] .p-art-plus-b{left:18%;bottom:13%}
[data-tcg-portal] .p-ecosystem-strip{border-bottom:1px solid var(--p-line)}[data-tcg-portal] .p-ecosystem-strip .p-container{display:flex;align-items:center;justify-content:space-between;gap:34px;min-height:119px}[data-tcg-portal] .p-ecosystem-strip p{font-size:10px;line-height:1.8;margin:0;padding-right:30px;border-right:1px solid var(--p-line)}[data-tcg-portal] .p-ecosystem-strip p strong{font-weight:500;color:#434e54}[data-tcg-portal] .p-ecosystem-logo{display:flex;align-items:center;opacity:.65;transition:opacity .2s}[data-tcg-portal] .p-ecosystem-logo:hover{opacity:1}[data-tcg-portal] .p-labvantage{font-size:25px;font-weight:400;letter-spacing:-1.4px}[data-tcg-portal] .p-labvantage>span:first-child{font-weight:700}[data-tcg-portal] .p-logo-dots{margin-left:8px;font-size:37px;font-weight:400}[data-tcg-portal] .p-biomax{gap:8px;font-size:30px;font-weight:500;letter-spacing:-1.2px}[data-tcg-portal] .p-lifesciences{font-size:29px;font-weight:700;gap:8px}[data-tcg-portal] .p-lifesciences>span{font-size:9px;letter-spacing:.06em;font-weight:600}[data-tcg-portal] .p-ecosystem-note{color:#626d72;font-size:10px;line-height:1.7;border-left:1px solid var(--p-line);padding-left:28px}
[data-tcg-portal] .p-section{padding-top:80px;padding-bottom:80px;scroll-margin-top:100px}[data-tcg-portal] .p-section-heading{display:flex;justify-content:space-between;align-items:flex-end;gap:30px;margin-bottom:34px}[data-tcg-portal] .p-section-heading h2{margin-bottom:12px}[data-tcg-portal] .p-section-heading p{font-size:13px;margin:0}[data-tcg-portal] .p-text-link{display:inline-flex;align-items:center;gap:15px;font-size:11px;font-weight:600;color:var(--p-ink);background:transparent;padding:0;border:0;white-space:nowrap;cursor:pointer}[data-tcg-portal] .p-text-link:hover{color:var(--p-orange)}[data-tcg-portal] .p-section-heading>.p-text-link{margin-bottom:5px}
[data-tcg-portal] .p-benefit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:23px}[data-tcg-portal] .p-benefit-card{border:1px solid var(--p-line);border-radius:7px;padding:26px 27px 29px;transition:transform .2s,box-shadow .2s}[data-tcg-portal] .p-benefit-card:hover{transform:translateY(-4px);box-shadow:0 12px 24px #192b3808}[data-tcg-portal] .p-benefit-top{display:flex;align-items:center;justify-content:space-between}[data-tcg-portal] .p-icon-tile{display:inline-grid;place-items:center;width:44px;height:44px;background:#fbefe5;color:#b96237;border-radius:8px;flex-shrink:0}[data-tcg-portal] .p-card-number{color:#626d72;font-size:10px;font-family:monospace}[data-tcg-portal] .p-benefit-card h3{margin:25px 0 11px;font-size:16px}[data-tcg-portal] .p-benefit-card p{font-size:12px;line-height:1.9;margin:0}[data-tcg-portal] .p-benefit-extras{display:grid;grid-template-columns:repeat(3,1fr);gap:35px;margin-top:50px}[data-tcg-portal] .p-benefit-extras>div>svg{color:var(--p-orange)}[data-tcg-portal] .p-benefit-extras h3{font-size:16px;margin-top:17px}[data-tcg-portal] .p-benefit-extras p{font-size:13px}
[data-tcg-portal] .p-solutions{background:#f7f7f4}[data-tcg-portal] .p-tabs{display:inline-flex;padding:4px;border:1px solid #dddfd9;border-radius:6px;gap:3px;flex-shrink:0}[data-tcg-portal] .p-tabs button{border:0;padding:7px 19px;font-size:11px;border-radius:3px;background:transparent;color:var(--p-muted)}[data-tcg-portal] .p-tabs button[aria-pressed="true"]{background:#fff;box-shadow:0 1px 5px #0000000c;color:var(--p-ink)}[data-tcg-portal] .p-product-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;animation:tcg-ez-fade .3s ease-out}[data-tcg-portal] .p-product-card{position:relative;overflow:hidden;min-height:306px;border:1px solid #dce2df;border-radius:7px;display:flex;align-items:center;padding:30px}[data-tcg-portal] .p-product-mcube{background:#eaf0ed}[data-tcg-portal] .p-product-lva{background:#eeedf3;border-color:#e1dfe7}[data-tcg-portal] .p-product-copy{z-index:1;width:70%;position:relative}[data-tcg-portal] .p-pill{display:inline-block;border:1px solid #b8c4bf;border-radius:3px;font-size:7px;line-height:1.5;letter-spacing:.12em;padding:5px 8px;font-weight:600;color:#52675e}[data-tcg-portal] .p-product-lva .p-pill{color:#6c627b;border-color:#cbc4d5}[data-tcg-portal] .p-product-copy h3{font-size:36px;line-height:1.12;margin:22px 0 15px;color:#30564f;letter-spacing:-.04em}[data-tcg-portal] .p-cube-name{font-weight:400}[data-tcg-portal] .p-product-copy h3 sup{font-size:12px;font-weight:400;vertical-align:top;line-height:2}[data-tcg-portal] .p-product-copy p{font-size:12px;line-height:1.9;color:#57695f;max-width:330px;margin-bottom:25px}[data-tcg-portal] .p-product-lva h3{color:#504268;font-size:26px}[data-tcg-portal] .p-product-lva p{color:#625c70}[data-tcg-portal] .p-product-subtitle{display:block;font-size:15px;margin-top:5px;font-weight:400}
[data-tcg-portal] .p-product-visual{position:absolute;inset:0;overflow:hidden;pointer-events:none}[data-tcg-portal] .p-cube{position:absolute;width:110px;height:110px;background:linear-gradient(135deg,#d3e4dd,#75968a);border:1px solid #79978755;border-radius:7px;transform:rotate(-30deg) skew(7deg,7deg);box-shadow:14px 17px 0 #62847355,26px 31px 0 #77998a20;right:-15px}[data-tcg-portal] .p-cube-one{top:43px;right:-7px}[data-tcg-portal] .p-cube-two{top:176px;right:17px;width:65px;height:65px;opacity:.6}[data-tcg-portal] .p-cube-three{top:260px;right:-32px;opacity:.4}[data-tcg-portal] .p-visual-cross{position:absolute;right:126px;top:63px;color:#8aa898;font-size:18px;font-weight:300}[data-tcg-portal] .p-molecule{position:absolute;width:200px;height:260px;right:-33px;top:48px;transform:rotate(-20deg)}[data-tcg-portal] .p-molecule span{position:absolute;border-radius:50%;background:radial-gradient(circle at 30% 25%,#eeecf6,#b0a2cc 60%,#81769c);width:56px;height:56px;z-index:1;box-shadow:7px 12px 20px #84709e12}[data-tcg-portal] .p-molecule span:nth-child(1){left:38px;top:55px;width:78px;height:78px}[data-tcg-portal] .p-molecule span:nth-child(2){left:135px;top:8px}[data-tcg-portal] .p-molecule span:nth-child(3){left:139px;top:145px}[data-tcg-portal] .p-molecule span:nth-child(4){left:19px;top:204px;width:35px;height:35px}[data-tcg-portal] .p-molecule span:nth-child(5){left:1px;top:8px;width:28px;height:28px;opacity:.5}[data-tcg-portal] .p-molecule i{position:absolute;height:10px;width:111px;background:linear-gradient(#ded7e9,#ad9bc5);left:56px;top:65px;transform:rotate(-33deg)}[data-tcg-portal] .p-molecule i:nth-of-type(2){top:139px;transform:rotate(45deg)}[data-tcg-portal] .p-molecule i:nth-of-type(3){left:2px;top:151px;transform:rotate(-73deg)}[data-tcg-portal] .p-product-note{display:flex;justify-content:center;align-items:center;gap:9px;margin-top:25px;color:#626d72;font-size:10px}[data-tcg-portal] .p-product-note svg{color:#9b9278}


[data-tcg-portal] .p-level-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:23px}[data-tcg-portal] .p-level-card{display:flex;flex-direction:column;border:1px solid var(--p-line);border-radius:7px;padding:28px}[data-tcg-portal] .p-level-featured{background:#faf7f2;border-color:#ddc8b6}[data-tcg-portal] .p-level-top{display:flex;align-items:center;justify-content:space-between}[data-tcg-portal] .p-level-index{font-size:8px;color:#626d72;letter-spacing:.13em}[data-tcg-portal] .p-level-card h3{font-size:21px;margin:23px 0 12px}[data-tcg-portal] .p-level-card>p{font-size:12px;line-height:1.9;margin:0;min-height:70px}[data-tcg-portal] .p-level-divider{height:1px;background:var(--p-line);margin:25px 0 22px}[data-tcg-portal] .p-mini-label{font-size:8px;letter-spacing:.13em;font-weight:600;color:#626d72}[data-tcg-portal] .p-level-card ul{list-style:none;padding:0;display:grid;gap:13px;margin:19px 0 29px}[data-tcg-portal] .p-level-card li{display:flex;align-items:flex-start;gap:9px;font-size:11px;line-height:1.5;color:#555f62}[data-tcg-portal] .p-level-card li svg{color:#79937e;margin-top:1px}[data-tcg-portal] .p-level-card .p-button{width:100%;margin-top:auto;justify-content:space-between;font-size:11px;padding:12px 14px;gap:10px}[data-tcg-portal] .p-level-footnote{margin-top:25px;display:flex;justify-content:space-between;gap:25px;font-size:10px;color:#626d72}[data-tcg-portal] .p-level-detail{margin-bottom:26px}[data-tcg-portal] .p-level-detail h4{font-size:12px;margin:20px 0 6px}[data-tcg-portal] .p-level-detail p{font-size:12px;margin:0}
[data-tcg-portal] .p-comparison{margin-top:30px;border:1px solid var(--p-line);border-radius:7px;overflow-x:auto}[data-tcg-portal] .p-comparison table{width:100%;border-collapse:collapse;min-width:690px;font-size:12px}[data-tcg-portal] .p-comparison caption{text-align:left;padding:24px;font-size:18px;font-weight:600}[data-tcg-portal] .p-comparison td,[data-tcg-portal] .p-comparison th{border-top:1px solid var(--p-line);padding:18px 22px;text-align:left;font-weight:400}[data-tcg-portal] .p-comparison th{font-weight:600}[data-tcg-portal] .p-comparison thead{background:var(--p-cream)}[data-tcg-portal] .p-comparison tbody th{width:25%}[data-tcg-portal] .p-comparison svg{color:#56816b;margin-right:5px}
[data-tcg-portal] .p-stories{background:#f8f7f4}[data-tcg-portal] .p-testimonial-card{display:grid;grid-template-columns:.77fr 1.23fr;border:1px solid #e3e4df;border-radius:7px;overflow:hidden;background:#fff}[data-tcg-portal] .p-testimonial-art{background:#e8ece8;padding:30px;position:relative;min-height:369px;display:flex;flex-direction:column;align-items:flex-start;overflow:hidden}[data-tcg-portal] .p-testimonial-art .p-pill{position:relative;z-index:2}[data-tcg-portal] .p-story-sculpture{width:200px;height:250px;position:absolute;right:38px;top:36px;transform:rotate(-28deg)}[data-tcg-portal] .p-story-sculpture span{position:absolute;border-radius:90px 90px 0 0;width:150px;height:220px;border:30px solid #7f9b8f;border-bottom:0;transform:skewY(10deg);box-shadow:inset 7px 8px 10px #405d5920,7px 0 0 #608373;background:#edf0e400}[data-tcg-portal] .p-story-sculpture span:nth-child(2){top:43px;left:37px;border-color:#b2c2a7;box-shadow:7px 0 0 #91a58a}[data-tcg-portal] .p-story-sculpture span:nth-child(3){top:86px;left:74px;border-color:#e0ceab;box-shadow:7px 0 0 #c6b28c}
[data-tcg-portal] .p-story-metric{margin-top:auto;z-index:1;width:calc(100% + 60px);margin-left:-30px;margin-bottom:-30px;padding:75px 30px 28px;background:linear-gradient(transparent,#e8ece8 60%)}[data-tcg-portal] .p-story-metric strong{display:block;font-family:Georgia,serif;font-size:37px;font-weight:400;letter-spacing:-.04em;color:#354e43}[data-tcg-portal] .p-story-metric>span{font-size:10px;color:#65776d}[data-tcg-portal] .p-testimonial-copy{padding:31px 40px}[data-tcg-portal] .p-story-meta{display:flex;align-items:center;justify-content:space-between;color:#626d72;font-size:9px}[data-tcg-portal] .p-demo-badge{border:1px solid #e1e4df;border-radius:3px;padding:3px 6px;font-size:8px}[data-tcg-portal] .p-quote-mark{display:block;color:#c96945;font-family:Georgia,serif;font-size:51px;height:47px;line-height:1.3;margin-top:14px}[data-tcg-portal] .p-testimonial-copy blockquote{font-size:21px;font-family:Manrope,sans-serif;letter-spacing:-.035em;line-height:1.6;margin:0 0 25px;animation:tcg-ez-fade .3s}[data-tcg-portal] .p-story-person{display:flex;align-items:center;gap:12px}[data-tcg-portal] .p-person-avatar{display:grid;place-items:center;width:38px;height:38px;border-radius:50%;color:#6e6045;background:#eee9dd;font-size:11px;font-weight:600;flex-shrink:0}[data-tcg-portal] .p-story-person strong{display:block;font-size:11px;font-weight:600}[data-tcg-portal] .p-story-person div>span{display:block;color:#626d72;font-size:9px;margin-top:2px}[data-tcg-portal] .p-story-bottom{border-top:1px solid var(--p-line);padding-top:20px;margin-top:24px;display:flex;align-items:center;justify-content:space-between;gap:12px}[data-tcg-portal] .p-carousel-controls{display:flex;align-items:center;gap:8px}[data-tcg-portal] .p-carousel-controls>span{font-size:9px;margin-right:12px}[data-tcg-portal] .p-carousel-controls>span>span{color:#626d72}[data-tcg-portal] .p-carousel-controls button{display:grid;place-items:center;padding:0;width:31px;height:31px;border:1px solid var(--p-line);border-radius:50%;background:#fff;color:var(--p-ink);transition:background .2s}[data-tcg-portal] .p-carousel-controls button:hover{background:#f2eee8}[data-tcg-portal] .p-story-detail{background:var(--p-cream);padding:18px;font-size:12px}[data-tcg-portal] .p-content-note{font-size:9px;margin:16px 0 0;line-height:1.8}
[data-tcg-portal] .p-story-selector{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:32px}[data-tcg-portal] .p-story-selector button{display:flex;gap:12px;align-items:center;text-align:left;padding:20px;background:#fff;color:var(--p-ink);border:1px solid var(--p-line);border-radius:6px}[data-tcg-portal] .p-story-selector button[aria-pressed="true"]{border-color:#b97953}[data-tcg-portal] .p-story-selector button>span:nth-child(2){flex:1}[data-tcg-portal] .p-story-selector strong{display:block;font-size:12px}[data-tcg-portal] .p-story-selector small{display:block;font-size:10px;color:var(--p-muted);margin-top:4px}
[data-tcg-portal] .p-cta-wrap{padding:72px 0}[data-tcg-portal] .p-cta{display:flex;align-items:center;justify-content:space-between;gap:35px;background:var(--p-navy);border-radius:8px;padding:49px 55px;color:#fff;position:relative;overflow:hidden;isolation:isolate}[data-tcg-portal] .p-cta .p-eyebrow{color:#c7b39b}[data-tcg-portal] .p-cta h2{font-size:39px;line-height:1.25;margin:17px 0}[data-tcg-portal] .p-cta h2 em{color:#edb48f}[data-tcg-portal] .p-cta p{font-size:12px;color:#b0bdc3;margin:0}[data-tcg-portal] .p-cta-action{display:flex;align-items:flex-start;flex-direction:column;gap:15px;z-index:1}[data-tcg-portal] .p-cta-action>span{color:#a0b1ba;font-size:9px}[data-tcg-portal] .p-cta-rings{position:absolute;border:1px solid #65869425;width:460px;height:460px;border-radius:50%;right:5%;top:-35%;z-index:-1}[data-tcg-portal] .p-cta-rings::before,[data-tcg-portal] .p-cta-rings::after{content:"";position:absolute;inset:48px;border:1px solid #65869425;border-radius:50%}[data-tcg-portal] .p-cta-rings::after{inset:100px}
[data-tcg-portal] .p-footer{border-top:1px solid var(--p-line);background:#fcfcfa}[data-tcg-portal] .p-footer-top{display:grid;grid-template-columns:1.2fr .9fr .9fr 1.25fr;gap:40px;padding:50px 0 43px}[data-tcg-portal] .p-footer .p-brand{margin-bottom:10px}[data-tcg-portal] .p-footer p{font-size:11px;line-height:1.9}[data-tcg-portal] .p-footer h3{margin:0 0 18px;font-size:11px;font-weight:700}[data-tcg-portal] .p-footer-top>div>a:not(.p-brand){display:flex;align-items:center;gap:7px;width:fit-content;font-size:10px;color:#69747a;margin-bottom:11px}[data-tcg-portal] .p-footer-top>div>a:hover{color:var(--p-orange)}[data-tcg-portal] .p-footer-top .p-footer-contact>.p-text-link{color:var(--p-orange);margin-top:22px}[data-tcg-portal] .p-footer-bottom{border-top:1px solid var(--p-line);padding:20px 0;display:flex;align-items:center;justify-content:space-between;font-size:9px;color:#626d72;gap:20px}[data-tcg-portal] .p-footer-bottom>span:last-child{display:flex;align-items:center;gap:7px}
[data-tcg-portal] .p-page-intro{padding:37px 0 70px;background:var(--p-cream);border-bottom:1px solid var(--p-line)}[data-tcg-portal] .p-breadcrumb{display:block;font-size:10px;margin-bottom:42px;color:#626d72!important}[data-tcg-portal] .p-breadcrumb span{margin-left:8px;color:#626d72}[data-tcg-portal] .p-page-intro h1{margin-top:22px;max-width:900px;font-size:55px}[data-tcg-portal] .p-page-intro p{max-width:630px;font-size:15px;line-height:1.9;margin:23px 0 0}
[data-tcg-portal] .p-ecosystem-feature{display:grid;grid-template-columns:1fr 1fr;gap:65px;align-items:center;background:#f7f5f0;padding:45px 50px;border-radius:8px}[data-tcg-portal] .p-ecosystem-feature p{font-size:13px;line-height:1.9}[data-tcg-portal] .p-ecosystem-feature .p-text-link{margin-top:12px}[data-tcg-portal] .p-ecosystem-diagram{position:relative;height:290px;border:1px solid #d7d2c3;border-radius:50%;margin:20px 35px}[data-tcg-portal] .p-ecosystem-diagram::before{content:"";position:absolute;inset:40px;border:1px dashed #d7d2c3;border-radius:50%}[data-tcg-portal] .p-ecosystem-center{display:flex;justify-content:center;align-items:center;flex-direction:column;background:var(--p-orange);color:#fff;width:120px;height:120px;border-radius:50%;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:30px;font-weight:700}[data-tcg-portal] .p-ecosystem-center small{font-size:7px;letter-spacing:.1em}[data-tcg-portal] .p-ecosystem-diagram>span:not(.p-ecosystem-center){position:absolute;background:#fff;border:1px solid var(--p-line);padding:13px 17px;border-radius:5px;font-size:11px}[data-tcg-portal] .p-ecosystem-diagram>span:nth-child(2){top:-15px;left:25%}[data-tcg-portal] .p-ecosystem-diagram>span:nth-child(3){top:55%;left:-30px}[data-tcg-portal] .p-ecosystem-diagram>span:nth-child(4){bottom:0;right:-10px}
[data-tcg-portal] .p-steps-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:48px}[data-tcg-portal] .p-step-number{display:block;font-size:37px;color:#cd805d;font-weight:400;font-family:Georgia,serif;border-bottom:1px solid var(--p-line);padding-bottom:18px;margin-bottom:22px}[data-tcg-portal] .p-steps-grid h3{font-size:18px;margin-bottom:10px}[data-tcg-portal] .p-steps-grid p{font-size:13px}[data-tcg-portal] .p-faq{display:grid;grid-template-columns:.9fr 1.2fr;gap:80px;border-top:1px solid var(--p-line)}[data-tcg-portal] .p-faq>div>p{font-size:12px}[data-tcg-portal] .p-faq .p-text-link{margin-top:16px}[data-tcg-portal] .p-accordion details{border-bottom:1px solid var(--p-line)}[data-tcg-portal] .p-accordion summary{display:flex;align-items:center;justify-content:space-between;gap:15px;list-style:none;cursor:pointer;padding:21px 0;font-size:13px;font-weight:500}[data-tcg-portal] .p-accordion summary::-webkit-details-marker{display:none}[data-tcg-portal] .p-accordion details[open] summary svg{transform:rotate(45deg)}[data-tcg-portal] .p-accordion details p{margin:0 0 25px;font-size:12px;line-height:1.9}[data-tcg-portal] .p-proof-section>p{font-size:13px}[data-tcg-portal] .p-proof-section>div{display:flex;gap:15px;flex-wrap:wrap;margin-top:25px}
[data-tcg-portal] .p-join-page{display:grid;grid-template-columns:.9fr 1.1fr;gap:90px;padding-top:40px;padding-bottom:85px}[data-tcg-portal] .p-join-intro h1{font-size:51px;margin:20px 0}[data-tcg-portal] .p-join-intro>p{font-size:14px;line-height:1.9;margin-bottom:38px}[data-tcg-portal] .p-join-promise{display:flex;align-items:flex-start;gap:16px;margin:25px 0}[data-tcg-portal] .p-join-promise strong{font-size:12px;font-weight:600}[data-tcg-portal] .p-join-promise p{font-size:11px;margin:5px 0 0;max-width:260px}[data-tcg-portal] .p-join-help{border-top:1px solid var(--p-line);padding-top:25px;margin-top:35px;font-size:11px;color:var(--p-muted)}[data-tcg-portal] .p-join-help .p-text-link{display:flex;width:fit-content;margin-top:8px}[data-tcg-portal] .p-join-decoration{font-family:Georgia,serif;font-size:75px;font-style:italic;color:#938371;line-height:1.2;display:block;margin-top:40px}[data-tcg-portal] .p-application{border:1px solid var(--p-line);border-radius:9px;background:#fff;align-self:start;margin-top:29px;box-shadow:0 15px 50px #3d342a06;overflow:hidden}[data-tcg-portal] .p-form-progress{list-style:none;margin:0;padding:26px 32px;display:flex;justify-content:space-between;gap:12px;background:#faf9f6;border-bottom:1px solid var(--p-line)}[data-tcg-portal] .p-form-progress button{display:flex;align-items:center;gap:9px;padding:0;background:transparent;color:#858a8c;font-size:11px;font-weight:500}[data-tcg-portal] .p-form-progress button>span{width:25px;height:25px;display:grid;place-items:center;border:1px solid #d6d8d3;border-radius:50%;font-size:10px}[data-tcg-portal] .p-form-progress .is-active button{color:var(--p-orange)}[data-tcg-portal] .p-form-progress .is-active button>span{background:var(--p-orange);border-color:var(--p-orange);color:#fff}
[data-tcg-portal] .p-join-form{padding:32px}[data-tcg-portal] .p-join-form h2{font-size:25px;margin-top:10px;outline:none}[data-tcg-portal] .p-form-description{font-size:12px;margin:0 0 25px}[data-tcg-portal] .p-form-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px 16px}[data-tcg-portal] .p-form-fields label{display:block;color:#394954;font-size:11px;font-weight:500}[data-tcg-portal] .p-form-fields label>span:not(.p-password-field){color:var(--p-orange)}[data-tcg-portal] .p-form-fields input,[data-tcg-portal] .p-form-fields select{display:block;width:100%;margin-top:8px;padding:12px 11px;background:#fff;border:1px solid #d9dedb;border-radius:4px;font-size:12px;min-height:44px}[data-tcg-portal] .p-form-fields input:focus,[data-tcg-portal] .p-form-fields select:focus{border-color:var(--p-orange);box-shadow:0 0 0 3px #d6532810}[data-tcg-portal] .p-form-fields input::placeholder{color:#919899;font-size:11px}[data-tcg-portal] .p-form-fields label>small{display:inline-block;margin-left:5px;color:#626d72;font-size:10px}[data-tcg-portal] .p-form-fields label>input~small,[data-tcg-portal] .p-form-fields label>select~small,[data-tcg-portal] .p-form-fields label>.p-password-field~small{display:block;margin:7px 0 0}[data-tcg-portal] .p-form-fields small a{text-decoration:underline;text-underline-offset:3px;color:#966044}[data-tcg-portal] .p-field-wide{grid-column:1/-1}[data-tcg-portal] .p-form-actions{display:flex;justify-content:flex-end;gap:12px;margin-top:30px}[data-tcg-portal] .p-form-actions .p-button:last-child{flex:1}[data-tcg-portal] .p-form-footnote{display:flex;gap:7px;align-items:center;justify-content:center;font-size:9px;line-height:1.6;margin:20px 0 0}[data-tcg-portal] .p-password-field{display:block;position:relative}[data-tcg-portal] .p-password-field input{padding-right:57px}[data-tcg-portal] .p-password-field button{position:absolute;right:8px;top:8px;bottom:8px;padding:0 5px;color:#626d72;background:transparent;font-size:10px}
[data-tcg-portal] .p-review-heading{display:flex;align-items:center;justify-content:space-between;margin:25px 0 15px}[data-tcg-portal] .p-review-heading h3{font-size:13px;margin:0}[data-tcg-portal] .p-review-heading button{background:transparent;color:var(--p-orange);font-size:11px;padding:5px}[data-tcg-portal] .p-review dl{display:grid;grid-template-columns:1fr 1.8fr;gap:11px;font-size:12px;border-bottom:1px solid var(--p-line);padding-bottom:24px}[data-tcg-portal] .p-review dt{color:var(--p-muted)}[data-tcg-portal] .p-review dd{margin:0;overflow-wrap:anywhere}[data-tcg-portal] .p-consent{display:flex;align-items:flex-start;gap:10px;margin-top:25px;font-size:11px;font-weight:400;color:#627078;line-height:1.8;cursor:pointer}[data-tcg-portal] .p-consent input{flex:0 0 16px;width:16px;height:16px;accent-color:var(--p-orange);margin:3px 0 0}[data-tcg-portal] .p-form-error{padding:15px;background:#fff1e9;border:1px solid #e9c2b2;border-radius:4px;color:#974a31;font-size:12px;margin:20px 0}[data-tcg-portal] .p-form-error button{display:block;margin-top:10px;color:#974a31;background:transparent;text-decoration:underline;padding:0;font-size:11px}
[data-tcg-portal] .p-join-success{max-width:680px;text-align:center;padding-block:70px}[data-tcg-portal] .p-join-success h1{font-size:44px;margin:20px 0;outline:none}[data-tcg-portal] .p-join-success>p{font-size:14px}[data-tcg-portal] .p-success-icon{display:grid;place-items:center;width:70px;height:70px;background:#e6eee5;color:#5e866e;border-radius:50%;margin:0 auto 30px}[data-tcg-portal] .p-reference{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:15px;margin:30px 0;padding:22px;background:var(--p-cream);border-radius:6px}[data-tcg-portal] .p-reference>span:first-child{font-size:8px;letter-spacing:.1em;color:var(--p-muted)}[data-tcg-portal] .p-reference strong{font-size:15px;letter-spacing:.05em}[data-tcg-portal] .p-pending-badge{font-size:10px;color:#795324;background:#efe5cf;padding:4px 9px;border-radius:4px}[data-tcg-portal] .p-next-steps{border:1px solid var(--p-line);border-radius:6px;padding:25px 35px;text-align:left;margin-bottom:30px}[data-tcg-portal] .p-next-steps h2{font-size:20px}[data-tcg-portal] .p-next-steps ol{padding-left:20px}[data-tcg-portal] .p-next-steps li{padding:9px 0 9px 9px;font-size:12px}[data-tcg-portal] .p-next-steps li strong,[data-tcg-portal] .p-next-steps li span{display:block}[data-tcg-portal] .p-next-steps li span{color:var(--p-muted);margin-top:4px}[data-tcg-portal] .p-join-success .p-hero-buttons{justify-content:center}
@keyframes tcg-ez-float{0%,100%{translate:0 0}50%{translate:0 -7px}}@keyframes tcg-ez-fade{from{opacity:.5;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}


@media(min-width:1500px){[data-tcg-portal] .p-hero-grid{min-height:620px}[data-tcg-portal] .p-network-art{height:555px}[data-tcg-portal] .p-hero-copy h1{font-size:68px}}
@media(max-width:1150px){
[data-tcg-portal] .p-container{width:calc(100% - 72px)}[data-tcg-portal] .p-nav{gap:18px}[data-tcg-portal] .p-nav>a{font-size:11px}[data-tcg-portal] .p-brand-label,[data-tcg-portal] .p-brand-divider{display:none}
[data-tcg-portal] .p-hero-copy h1{font-size:53px}[data-tcg-portal] .p-network-art{height:475px}[data-tcg-portal] .p-hero-grid{min-height:540px}[data-tcg-portal] .p-art-tag-top{left:0}[data-tcg-portal] .p-art-tag-right{right:-3%}
[data-tcg-portal] .p-ecosystem-note{display:none}[data-tcg-portal] .p-product-copy{width:78%}[data-tcg-portal] .p-product-visual,[data-tcg-portal] .p-molecule{opacity:.7}
[data-tcg-portal] .p-level-card{padding:24px 20px}[data-tcg-portal] .p-testimonial-copy{padding:28px}[data-tcg-portal] .p-testimonial-copy blockquote{font-size:19px}
[data-tcg-portal] .p-join-page{gap:45px}[data-tcg-portal] .p-join-intro h1{font-size:45px}[data-tcg-portal] .p-footer-top{gap:25px}[data-tcg-portal] .p-ecosystem-feature{gap:30px}[data-tcg-portal] .p-ecosystem-diagram{margin-inline:5px}}
@media(max-width:900px){
[data-tcg-portal] .p-header-inner{min-height:75px}[data-tcg-portal] .p-menu-toggle{display:block}[data-tcg-portal] .p-brand-label,[data-tcg-portal] .p-brand-divider{display:block}
[data-tcg-portal] .p-nav{display:none;position:absolute;top:100%;left:0;right:0;padding:22px 36px;background:#fff;box-shadow:0 20px 30px #142e3d10;border-bottom:1px solid var(--p-line)}
[data-tcg-portal] .p-nav.is-open{display:flex;align-items:stretch;flex-direction:column;gap:0}[data-tcg-portal] .p-nav>a{padding:14px 0;font-size:14px}[data-tcg-portal] .p-nav>a.active::after{display:none}[data-tcg-portal] .p-nav .p-login{padding:14px 0;border:none}[data-tcg-portal] .p-nav .p-button{margin-top:10px}
[data-tcg-portal] .p-hero-copy h1{font-size:46px}[data-tcg-portal] .p-hero-copy>p{font-size:13px}[data-tcg-portal] .p-network-art{height:425px}[data-tcg-portal] .p-art-tag strong{font-size:9px}[data-tcg-portal] .p-art-tag{gap:8px;padding:10px}[data-tcg-portal] .p-art-tag small{font-size:6px}[data-tcg-portal] .p-art-tag-left{font-size:8px;left:0}[data-tcg-portal] .p-art-coordinate{font-size:5px;bottom:16px}
[data-tcg-portal] .p-hero-buttons{gap:9px}[data-tcg-portal] .p-hero-buttons .p-button{padding:12px 15px;gap:12px;font-size:11px}[data-tcg-portal] .p-hero-note{font-size:9px}
[data-tcg-portal] .p-benefit-grid{gap:15px}[data-tcg-portal] .p-benefit-card{padding:22px 20px}[data-tcg-portal] .p-benefit-card h3{font-size:15px}
[data-tcg-portal] .p-section{padding-block:60px}[data-tcg-portal] .p-section-heading{align-items:flex-start}[data-tcg-portal] .p-section-heading>.p-text-link{font-size:10px;margin-top:31px}[data-tcg-portal] .p-section-heading h2{font-size:28px}[data-tcg-portal] .p-section-heading p{font-size:12px}
[data-tcg-portal] .p-product-card{padding:25px}[data-tcg-portal] .p-product-copy{width:100%}[data-tcg-portal] .p-product-visual,[data-tcg-portal] .p-molecule{opacity:.22}[data-tcg-portal] .p-product-copy p{max-width:270px}
[data-tcg-portal] .p-level-grid{gap:14px}[data-tcg-portal] .p-level-card h3{font-size:18px}[data-tcg-portal] .p-level-card>p{min-height:118px}[data-tcg-portal] .p-level-card .p-button{font-size:10px}[data-tcg-portal] .p-level-card li{font-size:10px}
[data-tcg-portal] .p-testimonial-card{grid-template-columns:.65fr 1fr}[data-tcg-portal] .p-testimonial-art{padding:24px}[data-tcg-portal] .p-story-metric{margin-left:-24px;margin-bottom:-24px;padding-left:24px}[data-tcg-portal] .p-story-metric strong{font-size:31px}[data-tcg-portal] .p-story-sculpture{right:0}[data-tcg-portal] .p-testimonial-copy{padding:24px}
[data-tcg-portal] .p-cta{padding:38px}[data-tcg-portal] .p-cta h2{font-size:33px}[data-tcg-portal] .p-cta-action>span{max-width:180px}[data-tcg-portal] .p-footer-top{grid-template-columns:repeat(2,1fr);gap:30px}
[data-tcg-portal] .p-page-intro h1{font-size:44px}[data-tcg-portal] .p-faq{gap:40px}[data-tcg-portal] .p-join-page{gap:30px;grid-template-columns:.8fr 1.2fr}[data-tcg-portal] .p-join-intro h1{font-size:36px}[data-tcg-portal] .p-join-form{padding:25px}[data-tcg-portal] .p-form-progress{padding:22px}[data-tcg-portal] .p-form-progress button{font-size:10px;gap:6px}[data-tcg-portal] .p-form-fields{grid-template-columns:1fr}[data-tcg-portal] .p-join-decoration{font-size:55px}
[data-tcg-portal] .p-story-selector{gap:12px}[data-tcg-portal] .p-story-selector button{padding:15px;flex-wrap:wrap}[data-tcg-portal] .p-story-selector strong{font-size:10px}[data-tcg-portal] .p-story-selector button>svg{display:none}}
@media(max-width:650px){
[data-tcg-portal] .p-container{width:calc(100% - 40px)}[data-tcg-portal] .p-announcement{font-size:9px;min-height:32px}[data-tcg-portal] .p-announcement>span{display:none}[data-tcg-portal] .p-header-inner{min-height:73px}[data-tcg-portal] .p-nav{padding:18px 20px}
[data-tcg-portal] .p-wordmark{font-size:24px}[data-tcg-portal] .p-wordmark>span{font-size:11px}[data-tcg-portal] .tcg-mark{width:30px}[data-tcg-portal] .p-brand-label{font-size:8px}[data-tcg-portal] .p-brand-divider{margin-left:10px}
[data-tcg-portal] .p-hero-grid{display:flex;flex-direction:column;gap:0;min-height:auto}[data-tcg-portal] .p-hero-copy{width:100%;padding:47px 0 0}[data-tcg-portal] .p-hero-copy h1{font-size:clamp(39px,9.5vw,54px);margin-top:21px;white-space:normal}[data-tcg-portal] .p-hero-copy>p{font-size:14px}[data-tcg-portal] .p-hero-note{font-size:10px;margin-top:25px}[data-tcg-portal] .p-hero-buttons .p-button{font-size:12px;padding:13px 16px}
[data-tcg-portal] .p-eyebrow{font-size:9px}[data-tcg-portal] .p-network-art{width:100%;max-width:430px;height:365px;margin:15px 0 18px}[data-tcg-portal] .p-globe-art{width:107%;height:107%;left:-3%;top:-1%}[data-tcg-portal] .p-art-tag-top{top:28px;left:10%}[data-tcg-portal] .p-art-tag-right{bottom:28px;right:0}[data-tcg-portal] .p-art-tag-left{top:61%;left:0}[data-tcg-portal] .p-art-coordinate{font-size:5px;bottom:0;left:20%}[data-tcg-portal] .p-art-tag strong{font-size:10px}[data-tcg-portal] .p-art-tag small{font-size:6px}[data-tcg-portal] .p-art-tag-left{font-size:9px}
[data-tcg-portal] .p-hero-bottom{padding-block:15px}[data-tcg-portal] .p-hero-bottom>span{max-width:150px;font-size:7px}[data-tcg-portal] .p-hero-bottom a{font-size:9px;gap:6px}
[data-tcg-portal] .p-ecosystem-strip .p-container{display:grid;grid-template-columns:1fr 1fr;gap:25px 20px;padding-block:28px}[data-tcg-portal] .p-ecosystem-strip p{border:none;padding:0}[data-tcg-portal] .p-labvantage{font-size:23px}[data-tcg-portal] .p-biomax{font-size:25px}[data-tcg-portal] .p-lifesciences{font-size:25px}[data-tcg-portal] .p-lifesciences>span{font-size:8px}[data-tcg-portal] .p-logo-dots{font-size:29px}
[data-tcg-portal] .p-section{padding-block:49px}[data-tcg-portal] .p-section-heading{flex-direction:column;gap:20px;margin-bottom:25px}[data-tcg-portal] .p-section-heading h2{font-size:29px;line-height:1.3}[data-tcg-portal] .p-section-heading p{font-size:13px;line-height:1.8}[data-tcg-portal] .p-section-heading>.p-text-link{margin-top:0;font-size:11px}
[data-tcg-portal] .p-benefit-grid,[data-tcg-portal] .p-product-grid,[data-tcg-portal] .p-level-grid,[data-tcg-portal] .p-benefit-extras{grid-template-columns:1fr;gap:17px}[data-tcg-portal] .p-benefit-card{padding:25px}[data-tcg-portal] .p-benefit-card h3{font-size:18px;margin-top:22px}[data-tcg-portal] .p-benefit-card p{font-size:13px}[data-tcg-portal] .p-benefit-extras{gap:25px;margin-top:35px}
[data-tcg-portal] .p-product-card{min-height:320px;padding:28px}[data-tcg-portal] .p-product-copy{width:84%}[data-tcg-portal] .p-product-visual,[data-tcg-portal] .p-molecule{opacity:.6}[data-tcg-portal] .p-product-copy p{font-size:12px}[data-tcg-portal] .p-product-note{align-items:flex-start;font-size:10px;text-align:center}[data-tcg-portal] .p-product-note svg{margin-top:2px}[data-tcg-portal] .p-product-note span{max-width:270px}
[data-tcg-portal] .p-level-card{padding:28px}[data-tcg-portal] .p-level-card h3{font-size:23px}[data-tcg-portal] .p-level-card>p{min-height:auto;font-size:13px}[data-tcg-portal] .p-level-card li{font-size:12px}[data-tcg-portal] .p-level-card .p-button{font-size:12px;padding:13px 16px}[data-tcg-portal] .p-level-footnote{flex-direction:column;gap:15px;font-size:10px}[data-tcg-portal] .p-level-detail p{font-size:13px}
[data-tcg-portal] .p-testimonial-card{grid-template-columns:1fr}[data-tcg-portal] .p-testimonial-art{min-height:245px}[data-tcg-portal] .p-story-sculpture{top:-35px;right:13%;transform:rotate(-28deg) scale(.85)}[data-tcg-portal] .p-story-metric{padding-top:30px}[data-tcg-portal] .p-story-metric strong{font-size:34px}[data-tcg-portal] .p-story-metric>span{font-size:11px}[data-tcg-portal] .p-testimonial-copy{padding:25px}[data-tcg-portal] .p-testimonial-copy blockquote{font-size:20px}[data-tcg-portal] .p-story-person strong{font-size:12px}[data-tcg-portal] .p-story-person div>span{font-size:10px}[data-tcg-portal] .p-story-meta{font-size:10px}[data-tcg-portal] .p-content-note{font-size:9px}
[data-tcg-portal] .p-story-selector{grid-template-columns:1fr;gap:10px}[data-tcg-portal] .p-story-selector button{padding:16px}[data-tcg-portal] .p-story-selector strong{font-size:12px}[data-tcg-portal] .p-story-selector button>svg{display:block}
[data-tcg-portal] .p-cta-wrap{padding-block:45px}[data-tcg-portal] .p-cta{flex-direction:column;align-items:flex-start;gap:28px;padding:32px 27px}[data-tcg-portal] .p-cta h2{font-size:35px}[data-tcg-portal] .p-cta p{font-size:12px}[data-tcg-portal] .p-cta-action{gap:12px}[data-tcg-portal] .p-cta-action>span{max-width:none}[data-tcg-portal] .p-cta-rings{right:-190px}
[data-tcg-portal] .p-footer-top{padding-block:35px;gap:30px 22px}[data-tcg-portal] .p-footer-top>div:first-child{grid-column:1/-1}[data-tcg-portal] .p-footer-top>div:last-child{grid-column:1/-1}[data-tcg-portal] .p-footer h3{font-size:12px}[data-tcg-portal] .p-footer-top>div>a:not(.p-brand){font-size:11px}[data-tcg-portal] .p-footer-bottom{flex-direction:column;align-items:flex-start;gap:10px;font-size:9px}
[data-tcg-portal] .p-page-intro{padding:25px 0 45px}[data-tcg-portal] .p-breadcrumb{margin-bottom:30px}[data-tcg-portal] .p-page-intro h1{font-size:40px}[data-tcg-portal] .p-page-intro p{font-size:14px}
[data-tcg-portal] .p-ecosystem-feature{grid-template-columns:1fr;padding:30px 25px;gap:35px}[data-tcg-portal] .p-ecosystem-feature h2{font-size:29px}[data-tcg-portal] .p-ecosystem-diagram{margin:20px;height:250px}[data-tcg-portal] .p-ecosystem-diagram>span:not(.p-ecosystem-center){font-size:9px;padding:10px}
[data-tcg-portal] .p-steps-grid{grid-template-columns:1fr;gap:24px}[data-tcg-portal] .p-step-number{font-size:29px;padding-bottom:10px;margin-bottom:14px}[data-tcg-portal] .p-steps-grid h3{font-size:19px}[data-tcg-portal] .p-faq{grid-template-columns:1fr;gap:25px}[data-tcg-portal] .p-faq h2{font-size:31px}[data-tcg-portal] .p-accordion summary{font-size:13px}[data-tcg-portal] .p-accordion details p{font-size:13px}
[data-tcg-portal] .p-join-page{display:flex;flex-direction:column;gap:10px;padding-top:25px;padding-bottom:50px}[data-tcg-portal] .p-join-intro h1{font-size:43px}[data-tcg-portal] .p-join-intro>p{font-size:14px;margin-bottom:22px}[data-tcg-portal] .p-join-promise,[data-tcg-portal] .p-join-decoration{display:none}[data-tcg-portal] .p-join-help{padding-top:15px;margin-top:20px}[data-tcg-portal] .p-application{width:100%;margin-top:25px}[data-tcg-portal] .p-join-form{padding:25px 22px}[data-tcg-portal] .p-form-progress{padding:21px 20px}[data-tcg-portal] .p-form-progress button{font-size:10px}[data-tcg-portal] .p-form-fields input,[data-tcg-portal] .p-form-fields select{font-size:16px}[data-tcg-portal] .p-form-fields label{font-size:12px}[data-tcg-portal] .p-form-footnote{font-size:9px}[data-tcg-portal] .p-join-success h1{font-size:36px}[data-tcg-portal] .p-next-steps{padding:20px}}
@media(prefers-reduced-motion:reduce){[data-tcg-portal] *,[data-tcg-portal] *::before,[data-tcg-portal] *::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}





[data-tcg-portal] [hidden]{display:none!important}
[data-tcg-portal] main{min-width:0;outline:none}
[data-tcg-portal] :is(h1,h2,h3){margin-top:0}
[data-tcg-portal] :is(.p-hero-grid,.p-join-page,.p-section-heading,.p-footer-top)>*{min-width:0}
[data-tcg-portal] .p-container{max-width:100%}
[data-tcg-portal] .p-menu-toggle{border:0;background:transparent}
[data-tcg-portal] .p-password-field button{padding:0 5px}
[data-tcg-portal] .p-form-progress button{padding:0;min-height:32px}
[data-tcg-portal] .p-tabs button{padding:7px 19px;color:var(--p-muted)}
[data-tcg-portal] .p-tabs button[aria-pressed="true"]{background:#fff;color:var(--p-ink)}
[data-tcg-portal] .p-text-link{padding:0}
[data-tcg-portal] .p-form-error button{padding:0;color:#974a31}
[data-tcg-portal] .p-form-fields fieldset,[data-tcg-portal] .p-capabilities{min-width:0;border:1px solid var(--p-line);border-radius:5px;margin:22px 0 0;padding:14px 16px}
[data-tcg-portal] .p-capabilities legend{padding:0 5px;font-size:12px;color:var(--p-ink)}
[data-tcg-portal] .p-capabilities .p-consent{margin:10px 0}
[data-tcg-portal] .p-form-loading{font-size:12px;color:var(--p-muted)}
[data-tcg-portal] .p-comparison{max-width:100%}
[data-tcg-portal] .p-review-heading button{padding:5px;color:var(--p-orange)}
[data-tcg-portal] .p-form-progress button:not(:disabled):focus-visible{outline-offset:3px}
[data-tcg-portal] .p-form-fields label>small{font-weight:400}
[data-tcg-portal] .p-footer a{overflow-wrap:anywhere}
@media(max-width:650px){[data-tcg-portal] .p-story-bottom{flex-wrap:wrap;row-gap:18px}[data-tcg-portal] .p-product-copy{width:100%}[data-tcg-portal] .p-product-copy .p-text-link{white-space:normal}[data-tcg-portal] .p-join-intro h1{font-size:clamp(35px,10vw,43px)}}
@media(max-width:360px){[data-tcg-portal] .p-container{width:calc(100% - 32px)}[data-tcg-portal] .p-brand-label,[data-tcg-portal] .p-brand-divider{display:none}[data-tcg-portal] .p-form-progress{padding:18px 12px;gap:7px}[data-tcg-portal] .p-form-progress button{gap:4px;font-size:9px}[data-tcg-portal] .p-join-form{padding:22px 16px}[data-tcg-portal] .p-cta{padding:28px 22px}[data-tcg-portal] .p-cta h2{font-size:31px}}


@container tcg-portal (min-width:1500px){[data-tcg-portal] .p-hero-grid{min-height:620px}[data-tcg-portal] .p-network-art{height:555px}[data-tcg-portal] .p-hero-copy h1{font-size:68px}}
@container tcg-portal (max-width:1150px){
[data-tcg-portal] .p-container{width:calc(100% - 72px)}[data-tcg-portal] .p-nav{gap:18px}[data-tcg-portal] .p-nav>a{font-size:11px}[data-tcg-portal] .p-brand-label,[data-tcg-portal] .p-brand-divider{display:none}
[data-tcg-portal] .p-hero-copy h1{font-size:53px}[data-tcg-portal] .p-network-art{height:475px}[data-tcg-portal] .p-hero-grid{min-height:540px}[data-tcg-portal] .p-art-tag-top{left:0}[data-tcg-portal] .p-art-tag-right{right:-3%}
[data-tcg-portal] .p-ecosystem-note{display:none}[data-tcg-portal] .p-product-copy{width:78%}[data-tcg-portal] .p-product-visual,[data-tcg-portal] .p-molecule{opacity:.7}
[data-tcg-portal] .p-level-card{padding:24px 20px}[data-tcg-portal] .p-testimonial-copy{padding:28px}[data-tcg-portal] .p-testimonial-copy blockquote{font-size:19px}
[data-tcg-portal] .p-join-page{gap:45px}[data-tcg-portal] .p-join-intro h1{font-size:45px}[data-tcg-portal] .p-footer-top{gap:25px}[data-tcg-portal] .p-ecosystem-feature{gap:30px}[data-tcg-portal] .p-ecosystem-diagram{margin-inline:5px}}
@container tcg-portal (max-width:900px){
[data-tcg-portal] .p-header-inner{min-height:75px}[data-tcg-portal] .p-menu-toggle{display:block}[data-tcg-portal] .p-brand-label,[data-tcg-portal] .p-brand-divider{display:block}
[data-tcg-portal] .p-nav{display:none;position:absolute;top:100%;left:0;right:0;padding:22px 36px;background:#fff;box-shadow:0 20px 30px #142e3d10;border-bottom:1px solid var(--p-line)}
[data-tcg-portal] .p-nav.is-open{display:flex;align-items:stretch;flex-direction:column;gap:0}[data-tcg-portal] .p-nav>a{padding:14px 0;font-size:14px}[data-tcg-portal] .p-nav>a.active::after{display:none}[data-tcg-portal] .p-nav .p-login{padding:14px 0;border:none}[data-tcg-portal] .p-nav .p-button{margin-top:10px}
[data-tcg-portal] .p-hero-copy h1{font-size:46px}[data-tcg-portal] .p-hero-copy>p{font-size:13px}[data-tcg-portal] .p-network-art{height:425px}[data-tcg-portal] .p-art-tag strong{font-size:9px}[data-tcg-portal] .p-art-tag{gap:8px;padding:10px}[data-tcg-portal] .p-art-tag small{font-size:6px}[data-tcg-portal] .p-art-tag-left{font-size:8px;left:0}[data-tcg-portal] .p-art-coordinate{font-size:5px;bottom:16px}
[data-tcg-portal] .p-hero-buttons{gap:9px}[data-tcg-portal] .p-hero-buttons .p-button{padding:12px 15px;gap:12px;font-size:11px}[data-tcg-portal] .p-hero-note{font-size:9px}
[data-tcg-portal] .p-benefit-grid{gap:15px}[data-tcg-portal] .p-benefit-card{padding:22px 20px}[data-tcg-portal] .p-benefit-card h3{font-size:15px}
[data-tcg-portal] .p-section{padding-block:60px}[data-tcg-portal] .p-section-heading{align-items:flex-start}[data-tcg-portal] .p-section-heading>.p-text-link{font-size:10px;margin-top:31px}[data-tcg-portal] .p-section-heading h2{font-size:28px}[data-tcg-portal] .p-section-heading p{font-size:12px}
[data-tcg-portal] .p-product-card{padding:25px}[data-tcg-portal] .p-product-copy{width:100%}[data-tcg-portal] .p-product-visual,[data-tcg-portal] .p-molecule{opacity:.22}[data-tcg-portal] .p-product-copy p{max-width:270px}
[data-tcg-portal] .p-level-grid{gap:14px}[data-tcg-portal] .p-level-card h3{font-size:18px}[data-tcg-portal] .p-level-card>p{min-height:118px}[data-tcg-portal] .p-level-card .p-button{font-size:10px}[data-tcg-portal] .p-level-card li{font-size:10px}
[data-tcg-portal] .p-testimonial-card{grid-template-columns:.65fr 1fr}[data-tcg-portal] .p-testimonial-art{padding:24px}[data-tcg-portal] .p-story-metric{margin-left:-24px;margin-bottom:-24px;padding-left:24px}[data-tcg-portal] .p-story-metric strong{font-size:31px}[data-tcg-portal] .p-story-sculpture{right:0}[data-tcg-portal] .p-testimonial-copy{padding:24px}
[data-tcg-portal] .p-cta{padding:38px}[data-tcg-portal] .p-cta h2{font-size:33px}[data-tcg-portal] .p-cta-action>span{max-width:180px}[data-tcg-portal] .p-footer-top{grid-template-columns:repeat(2,1fr);gap:30px}
[data-tcg-portal] .p-page-intro h1{font-size:44px}[data-tcg-portal] .p-faq{gap:40px}[data-tcg-portal] .p-join-page{gap:30px;grid-template-columns:.8fr 1.2fr}[data-tcg-portal] .p-join-intro h1{font-size:36px}[data-tcg-portal] .p-join-form{padding:25px}[data-tcg-portal] .p-form-progress{padding:22px}[data-tcg-portal] .p-form-progress button{font-size:10px;gap:6px}[data-tcg-portal] .p-form-fields{grid-template-columns:1fr}[data-tcg-portal] .p-join-decoration{font-size:55px}
[data-tcg-portal] .p-story-selector{gap:12px}[data-tcg-portal] .p-story-selector button{padding:15px;flex-wrap:wrap}[data-tcg-portal] .p-story-selector strong{font-size:10px}[data-tcg-portal] .p-story-selector button>svg{display:none}}
@container tcg-portal (max-width:650px){
[data-tcg-portal] .p-container{width:calc(100% - 40px)}[data-tcg-portal] .p-announcement{font-size:9px;min-height:32px}[data-tcg-portal] .p-announcement>span{display:none}[data-tcg-portal] .p-header-inner{min-height:73px}[data-tcg-portal] .p-nav{padding:18px 20px}
[data-tcg-portal] .p-wordmark{font-size:24px}[data-tcg-portal] .p-wordmark>span{font-size:11px}[data-tcg-portal] .tcg-mark{width:30px}[data-tcg-portal] .p-brand-label{font-size:8px}[data-tcg-portal] .p-brand-divider{margin-left:10px}
[data-tcg-portal] .p-hero-grid{display:flex;flex-direction:column;gap:0;min-height:auto}[data-tcg-portal] .p-hero-copy{width:100%;padding:47px 0 0}[data-tcg-portal] .p-hero-copy h1{font-size:clamp(39px,9.5vw,54px);margin-top:21px;white-space:normal}[data-tcg-portal] .p-hero-copy>p{font-size:14px}[data-tcg-portal] .p-hero-note{font-size:10px;margin-top:25px}[data-tcg-portal] .p-hero-buttons .p-button{font-size:12px;padding:13px 16px}
[data-tcg-portal] .p-eyebrow{font-size:9px}[data-tcg-portal] .p-network-art{width:100%;max-width:430px;height:365px;margin:15px 0 18px}[data-tcg-portal] .p-globe-art{width:107%;height:107%;left:-3%;top:-1%}[data-tcg-portal] .p-art-tag-top{top:28px;left:10%}[data-tcg-portal] .p-art-tag-right{bottom:28px;right:0}[data-tcg-portal] .p-art-tag-left{top:61%;left:0}[data-tcg-portal] .p-art-coordinate{font-size:5px;bottom:0;left:20%}[data-tcg-portal] .p-art-tag strong{font-size:10px}[data-tcg-portal] .p-art-tag small{font-size:6px}[data-tcg-portal] .p-art-tag-left{font-size:9px}
[data-tcg-portal] .p-hero-bottom{padding-block:15px}[data-tcg-portal] .p-hero-bottom>span{max-width:150px;font-size:7px}[data-tcg-portal] .p-hero-bottom a{font-size:9px;gap:6px}
[data-tcg-portal] .p-ecosystem-strip .p-container{display:grid;grid-template-columns:1fr 1fr;gap:25px 20px;padding-block:28px}[data-tcg-portal] .p-ecosystem-strip p{border:none;padding:0}[data-tcg-portal] .p-labvantage{font-size:23px}[data-tcg-portal] .p-biomax{font-size:25px}[data-tcg-portal] .p-lifesciences{font-size:25px}[data-tcg-portal] .p-lifesciences>span{font-size:8px}[data-tcg-portal] .p-logo-dots{font-size:29px}
[data-tcg-portal] .p-section{padding-block:49px}[data-tcg-portal] .p-section-heading{flex-direction:column;gap:20px;margin-bottom:25px}[data-tcg-portal] .p-section-heading h2{font-size:29px;line-height:1.3}[data-tcg-portal] .p-section-heading p{font-size:13px;line-height:1.8}[data-tcg-portal] .p-section-heading>.p-text-link{margin-top:0;font-size:11px}
[data-tcg-portal] .p-benefit-grid,[data-tcg-portal] .p-product-grid,[data-tcg-portal] .p-level-grid,[data-tcg-portal] .p-benefit-extras{grid-template-columns:1fr;gap:17px}[data-tcg-portal] .p-benefit-card{padding:25px}[data-tcg-portal] .p-benefit-card h3{font-size:18px;margin-top:22px}[data-tcg-portal] .p-benefit-card p{font-size:13px}[data-tcg-portal] .p-benefit-extras{gap:25px;margin-top:35px}
[data-tcg-portal] .p-product-card{min-height:320px;padding:28px}[data-tcg-portal] .p-product-copy{width:84%}[data-tcg-portal] .p-product-visual,[data-tcg-portal] .p-molecule{opacity:.6}[data-tcg-portal] .p-product-copy p{font-size:12px}[data-tcg-portal] .p-product-note{align-items:flex-start;font-size:10px;text-align:center}[data-tcg-portal] .p-product-note svg{margin-top:2px}[data-tcg-portal] .p-product-note span{max-width:270px}
[data-tcg-portal] .p-level-card{padding:28px}[data-tcg-portal] .p-level-card h3{font-size:23px}[data-tcg-portal] .p-level-card>p{min-height:auto;font-size:13px}[data-tcg-portal] .p-level-card li{font-size:12px}[data-tcg-portal] .p-level-card .p-button{font-size:12px;padding:13px 16px}[data-tcg-portal] .p-level-footnote{flex-direction:column;gap:15px;font-size:10px}[data-tcg-portal] .p-level-detail p{font-size:13px}
[data-tcg-portal] .p-testimonial-card{grid-template-columns:1fr}[data-tcg-portal] .p-testimonial-art{min-height:245px}[data-tcg-portal] .p-story-sculpture{top:-35px;right:13%;transform:rotate(-28deg) scale(.85)}[data-tcg-portal] .p-story-metric{padding-top:30px}[data-tcg-portal] .p-story-metric strong{font-size:34px}[data-tcg-portal] .p-story-metric>span{font-size:11px}[data-tcg-portal] .p-testimonial-copy{padding:25px}[data-tcg-portal] .p-testimonial-copy blockquote{font-size:20px}[data-tcg-portal] .p-story-person strong{font-size:12px}[data-tcg-portal] .p-story-person div>span{font-size:10px}[data-tcg-portal] .p-story-meta{font-size:10px}[data-tcg-portal] .p-content-note{font-size:9px}
[data-tcg-portal] .p-story-selector{grid-template-columns:1fr;gap:10px}[data-tcg-portal] .p-story-selector button{padding:16px}[data-tcg-portal] .p-story-selector strong{font-size:12px}[data-tcg-portal] .p-story-selector button>svg{display:block}
[data-tcg-portal] .p-cta-wrap{padding-block:45px}[data-tcg-portal] .p-cta{flex-direction:column;align-items:flex-start;gap:28px;padding:32px 27px}[data-tcg-portal] .p-cta h2{font-size:35px}[data-tcg-portal] .p-cta p{font-size:12px}[data-tcg-portal] .p-cta-action{gap:12px}[data-tcg-portal] .p-cta-action>span{max-width:none}[data-tcg-portal] .p-cta-rings{right:-190px}
[data-tcg-portal] .p-footer-top{padding-block:35px;gap:30px 22px}[data-tcg-portal] .p-footer-top>div:first-child{grid-column:1/-1}[data-tcg-portal] .p-footer-top>div:last-child{grid-column:1/-1}[data-tcg-portal] .p-footer h3{font-size:12px}[data-tcg-portal] .p-footer-top>div>a:not(.p-brand){font-size:11px}[data-tcg-portal] .p-footer-bottom{flex-direction:column;align-items:flex-start;gap:10px;font-size:9px}
[data-tcg-portal] .p-page-intro{padding:25px 0 45px}[data-tcg-portal] .p-breadcrumb{margin-bottom:30px}[data-tcg-portal] .p-page-intro h1{font-size:40px}[data-tcg-portal] .p-page-intro p{font-size:14px}
[data-tcg-portal] .p-ecosystem-feature{grid-template-columns:1fr;padding:30px 25px;gap:35px}[data-tcg-portal] .p-ecosystem-feature h2{font-size:29px}[data-tcg-portal] .p-ecosystem-diagram{margin:20px;height:250px}[data-tcg-portal] .p-ecosystem-diagram>span:not(.p-ecosystem-center){font-size:9px;padding:10px}
[data-tcg-portal] .p-steps-grid{grid-template-columns:1fr;gap:24px}[data-tcg-portal] .p-step-number{font-size:29px;padding-bottom:10px;margin-bottom:14px}[data-tcg-portal] .p-steps-grid h3{font-size:19px}[data-tcg-portal] .p-faq{grid-template-columns:1fr;gap:25px}[data-tcg-portal] .p-faq h2{font-size:31px}[data-tcg-portal] .p-accordion summary{font-size:13px}[data-tcg-portal] .p-accordion details p{font-size:13px}
[data-tcg-portal] .p-join-page{display:flex;flex-direction:column;gap:10px;padding-top:25px;padding-bottom:50px}[data-tcg-portal] .p-join-intro h1{font-size:43px}[data-tcg-portal] .p-join-intro>p{font-size:14px;margin-bottom:22px}[data-tcg-portal] .p-join-promise,[data-tcg-portal] .p-join-decoration{display:none}[data-tcg-portal] .p-join-help{padding-top:15px;margin-top:20px}[data-tcg-portal] .p-application{width:100%;margin-top:25px}[data-tcg-portal] .p-join-form{padding:25px 22px}[data-tcg-portal] .p-form-progress{padding:21px 20px}[data-tcg-portal] .p-form-progress button{font-size:10px}[data-tcg-portal] .p-form-fields input,[data-tcg-portal] .p-form-fields select{font-size:16px}[data-tcg-portal] .p-form-fields label{font-size:12px}[data-tcg-portal] .p-form-footnote{font-size:9px}[data-tcg-portal] .p-join-success h1{font-size:36px}[data-tcg-portal] .p-next-steps{padding:20px}}
@container tcg-portal (max-width:650px){[data-tcg-portal] .p-story-bottom{flex-wrap:wrap;row-gap:18px}[data-tcg-portal] .p-product-copy{width:100%}[data-tcg-portal] .p-product-copy .p-text-link{white-space:normal}[data-tcg-portal] .p-join-intro h1{font-size:clamp(35px,10vw,43px)}}
@container tcg-portal (max-width:360px){[data-tcg-portal] .p-container{width:calc(100% - 32px)}[data-tcg-portal] .p-brand-label,[data-tcg-portal] .p-brand-divider{display:none}[data-tcg-portal] .p-form-progress{padding:18px 12px;gap:7px}[data-tcg-portal] .p-form-progress button{gap:4px;font-size:9px}[data-tcg-portal] .p-join-form{padding:22px 16px}[data-tcg-portal] .p-cta{padding:28px 22px}[data-tcg-portal] .p-cta h2{font-size:31px}}
`;
    const partnerPaths = [
        { code: "REFERRAL", name: "Referral partner", verb: "Connect.", icon: "people", tag: "Turn relationships into opportunity", description: "Open new doors. Introduce businesses to TCG and let our team take the opportunity forward.", audience: "Advisors, consultants, and industry connectors with an established business network.", requirements: "A registered business, a relevant network, and qualified customer introductions.", incentive: "Referral commission on explicitly eligible revenue, subject to approved agreement and successful conversion.", benefits: ["A simple opportunity referral process", "Visibility into approved referral progress", "TCG-led sales and implementation"], },
        { code: "RESELLER", name: "Reseller partner", verb: "Grow.", icon: "growth", tag: "Make more possible for your customers", description: "Bring TCG solutions to your market and build lasting value through your customer relationships.", audience: "Technology providers and sales organizations with enterprise customer relationships.", requirements: "A registered business, a sales capability, and an agreed go-to-market plan.", incentive: "Earn the margin between your customer selling price and your agreed TCG wholesale price.", benefits: ["An expanded enterprise solution portfolio", "Ownership of your customer relationship", "Agreed wholesale commercial terms"], },
        { code: "SYSTEM_INTEGRATOR", name: "System integrator", verb: "Build.", icon: "layers", tag: "Your expertise. Our technology.", description: "Combine your delivery expertise with TCG platforms to solve your customers’ most complex challenges.", audience: "Consultancies and delivery teams with integration, data, or industry expertise.", requirements: "A registered business, implementation expertise, and an agreed project delivery scope.", incentive: "Project-based service value and allocations agreed in your individual contract.", benefits: ["Joint solution and delivery opportunities", "Integration with TCG platforms", "Project-specific roles and commercial terms"], },
    ];
    const benefits = [
        { icon: "growth", title: "Unlock new growth", text: "Expand your offering with enterprise AI and analytics. Turn your market knowledge into new business opportunities." },
        { icon: "spark", title: "Build with powerful technology", text: "Bring together your expertise and TCG’s intelligent platforms to create solutions that make a difference." },
        { icon: "people", title: "Succeed, together", text: "Work with a team that understands your ambition. Align on opportunities, delivery, and a shared path forward." },
    ];
    const stories = [
        { company: "Northstar Consulting", initials: "NC", person: "Alex Morgan", role: "Managing Partner", type: "System integrator", quote: "Bringing our industry expertise together with TCG’s technology gives us a new way to solve our customers’ most important challenges.", metric: "One team.", metricLabel: "A shared approach to customer success", detail: "This illustrative scenario shows a consulting team combining its implementation expertise with TCG analytics. The teams agree on delivery ownership and commercial terms before working toward a shared customer outcome." },
        { company: "Meridian Technologies", initials: "MT", person: "Priya Shah", role: "Director of Partnerships", type: "Reseller partner", quote: "The opportunity to add enterprise analytics to our portfolio helps us have a much more valuable conversation with our customers.", metric: "More possibility.", metricLabel: "An expanded enterprise solution portfolio", detail: "This illustrative reseller scenario shows a technology provider introducing TCG solutions to its customers. The reseller owns the customer relationship and sets its customer price under an agreed wholesale arrangement." },
        { company: "Apex Advisory", initials: "AA", person: "Daniel Lee", role: "Founder", type: "Referral partner", quote: "We know our customers’ challenges. A clear referral path lets us connect them with the right technology and the right people.", metric: "Better connected.", metricLabel: "Relationships that open new doors", detail: "This illustrative referral scenario shows an advisor introducing a qualified opportunity. TCG leads the sales and delivery process, while the advisor follows approved progress and earns compensation under the agreed referral terms." },
    ];
    const faqs = [
        ["Which partnership is right for my business?", "Choose Referral if you introduce opportunities, Reseller if you own the customer sales relationship, or System Integrator if you implement solutions. Start with your primary interest; TCG can discuss additional capabilities during review."],
        ["Are these partnership types ranked tiers?", "No. Referral, Reseller, and System Integrator are distinct ways to work with TCG, with different responsibilities and commercial arrangements. Choose the model that fits how you serve customers."],
        ["What do I need to apply?", "Have your company name, business email, country, primary contact details, and preferred partnership type ready. You’ll also create a password for your future partner workspace."],
        ["What happens after I submit my application?", "TCG reviews your company and partnership interests. The team can contact your primary administrator for clarification, agree on the appropriate terms, and approve workspace access when onboarding is complete."],
        ["How are commercial benefits determined?", "Resellers earn their agreed customer-to-wholesale margin. Referral benefits apply to explicitly eligible revenue after successful conversion. System integrator allocations follow project terms. Exact eligibility and commercial conditions are agreed with TCG."],
    ];

    const paths = {
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
    function Icon({ name = "arrow", size = 20, style }) {
        return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name] ?? paths.arrow}/></svg>;
    }
    function TcgMark() {
        return <svg className="tcg-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M7 30V10h25M14 30V17h18M21 30V24h11" stroke="currentColor" strokeWidth="4.5"/></svg>;
    }

    function NetworkArt() {
        return <div className="p-network-art" role="img" aria-label="An interconnected globe representing TCG's partner ecosystem">
        <div className="p-art-grid"/>
        <div className="p-art-orbit p-art-orbit-one"/><div className="p-art-orbit p-art-orbit-two"/>
        <svg className="p-globe-art" viewBox="0 0 600 600" fill="none" aria-hidden="true">
          <defs>
            <radialGradient id={id("globe-fill")} cx=".32" cy=".25" r=".85"><stop stopColor="#fffaf1"/><stop offset=".5" stopColor="#f7d3b3"/><stop offset="1" stopColor="#c65c2c"/></radialGradient>
            <linearGradient id={id("globe-lines")} x1="140" y1="100" x2="460" y2="500" gradientUnits="userSpaceOnUse"><stop stopColor="#db793b"/><stop offset=".5" stopColor="#e8a579"/><stop offset="1" stopColor="#a04622"/></linearGradient>
            <linearGradient id={id("ribbon")} x1="100" y1="100" x2="500" y2="460" gradientUnits="userSpaceOnUse"><stop stopColor="#fe9149"/><stop offset=".55" stopColor="#ed6b30"/><stop offset="1" stopColor="#bc411a"/></linearGradient>
            <filter id={id("globe-shadow")}><feDropShadow dx="5" dy="24" stdDeviation="20" floodColor="#a75c31" floodOpacity=".16"/></filter>
            <clipPath id={id("globe-clip")}><circle cx="300" cy="300" r="179"/></clipPath>
          </defs>
          <g filter={`url(#${id("globe-shadow")})`}><circle cx="300" cy="300" r="179" fill={`url(#${id("globe-fill")})`}/>
            <g clipPath={`url(#${id("globe-clip")})`} stroke={`url(#${id("globe-lines")})`} strokeWidth=".8" opacity=".65" transform="rotate(-22 300 300)">
              {[32, 65, 100, 140, 177].map((rx) => <ellipse key={rx} cx="300" cy="300" rx={rx} ry="179"/>)}
              {[145, 178, 216, 258, 300, 342, 384, 422, 455].map((cy) => <ellipse key={cy} cx="300" cy={cy} rx="184" ry="31"/>)}
            </g>
          </g>
          <ellipse cx="300" cy="300" rx="249" ry="90" transform="rotate(-38 300 300)" stroke="#d57442" strokeWidth="1" strokeDasharray="4 6" opacity=".55"/>
          <path d="M136 201C78 260 102 380 236 431c122 46 259 7 265-53" stroke={`url(#${id("ribbon")})`} strokeWidth="29"/>
          <path d="M136 201C78 260 102 380 236 431c122 46 259 7 265-53" stroke="#ffb576" strokeWidth="1.5" transform="translate(0 -14)" opacity=".75"/>
          <path d="M391 153c-84-75-243-48-295 39" stroke={`url(#${id("ribbon")})`} strokeWidth="13"/>
          <g fill="#fff9f2" stroke="#cf6c34"><circle cx="178" cy="215" r="6"/><circle cx="402" cy="219" r="5"/><circle cx="333" cy="397" r="5"/><circle cx="261" cy="163" r="4"/><circle cx="458" cy="316" r="4"/></g>
          <g stroke="#ad6d4a" strokeDasharray="3 5" opacity=".7"><path d="m178 215 83-52 141 56-69 178-155-182 224 4 56 97-125 81"/></g>
        </svg>
        <div className="p-art-tag p-art-tag-top"><span className="p-icon-tile"><Icon name="network"/></span><span><small>ONE CONNECTED ECOSYSTEM</small><strong>More possibility. Together.</strong></span><span className="p-live-dot"/></div>
        <div className="p-art-tag p-art-tag-left"><Icon name="code" size={18}/><span>Build with confidence</span></div>
        <div className="p-art-tag p-art-tag-right"><span className="p-art-arrow"><Icon name="growth" size={21}/></span><span><small>SHARED AMBITION</small><strong>Limitless potential</strong></span></div>
        <span className="p-art-coordinate">CONNECTED BY EXPERTISE. UNITED BY POSSIBILITY.</span>
        <span className="p-art-plus p-art-plus-a">+</span><span className="p-art-plus p-art-plus-b">+</span>
      </div>;
    }

    function SectionHeading({ eyebrow, title, description, children }) {
        return <div className="p-section-heading"><div><span className="p-eyebrow">{eyebrow}</span><h2>{title}</h2>{description && <p>{description}</p>}</div>{children}</div>;
    }
    function Benefits({ extended = false }) {
        return <section className="p-section p-container" id={id("benefits")}>
        <SectionHeading eyebrow="THE POWER OF PARTNERSHIP" title="Your ambition. Our shared advantage." description="More than a partnership. A foundation for what comes next.">
          {!extended && <Link className="p-text-link" to="/partner-with-tcg">Why partner with TCG <Icon size={17}/></Link>}
        </SectionHeading>
        <div className="p-benefit-grid">{benefits.map((benefit, i) => <article className="p-benefit-card" key={benefit.title}><div className="p-benefit-top"><span className="p-icon-tile"><Icon name={benefit.icon} size={24}/></span><span className="p-card-number">0{i + 1}</span></div><h3>{benefit.title}</h3><p>{benefit.text}</p></article>)}</div>
        {extended && <div className="p-benefit-extras"><div><Icon name="book"/><h3>Knowledge that moves you forward</h3><p>Align your team on product knowledge, solution design, and the resources available within your partnership.</p></div><div><Icon name="shield"/><h3>A workspace for your business</h3><p>Manage authorized opportunities and access the information your team needs through the partner portal.</p></div><div><Icon name="network"/><h3>A connected ecosystem</h3><p>Collaborate across technology, industry, and delivery disciplines to create meaningful customer outcomes.</p></div></div>}
      </section>;
    }
    function Products() {
        const [active, setActive] = useState("Platforms");
        const platforms = active === "Platforms";
        return <section className="p-solutions p-section" id={id("solutions")}><div className="p-container">
        <SectionHeading eyebrow="INNOVATION YOU CAN BUILD ON" title="Powerful platforms. Real-world possibilities." description="Bring intelligent solutions to the businesses that need them.">
          <div className="p-tabs" aria-label="Solution category">{["Platforms", "Services"].map(tab => <button key={tab} aria-pressed={active === tab} onClick={() => setActive(tab)}>{tab}</button>)}</div>
        </SectionHeading>
        <div className="p-product-grid" key={active}>
          <article className="p-product-card p-product-mcube"><div className="p-product-copy"><span className="p-pill">{platforms ? "ENTERPRISE AI & ANALYTICS" : "DATA & AI SERVICES"}</span><h3>{platforms ? <>m<span className="p-cube-name">cube</span><sup>™</sup></> : "Intelligence, applied."}</h3><p>{platforms ? "Turn enterprise data into decisions. An end-to-end AI and analytics platform that connects insights to business impact." : "Connect your data strategy to your business ambition with TCG’s enterprise AI and digital transformation expertise."}</p><a href={platforms ? "https://www.tcgdigital.com/tcg-mcube/" : "https://www.tcgdigital.com/"} target="_blank" rel="noreferrer" className="p-text-link">Explore {platforms ? "mcube" : "TCG services"} <Icon name="diagonal" size={17}/></a></div><div className="p-product-visual" aria-hidden="true"><div className="p-cube p-cube-one"/><div className="p-cube p-cube-two"/><div className="p-cube p-cube-three"/><div className="p-visual-cross">+</div></div></article>
          <article className="p-product-card p-product-lva"><div className="p-product-copy"><span className="p-pill">{platforms ? "LABORATORY INTELLIGENCE" : "INDUSTRY EXPERTISE"}</span><h3>{platforms ? <>LabVantage<span className="p-product-subtitle">Analytics</span></> : "Built around your industry."}</h3><p>{platforms ? "Make every discovery count. Bring self-service analytics, predictive insight, and AI to laboratory data." : "From life sciences to industrial operations, bring domain knowledge and intelligent platforms together."}</p><a href={platforms ? "https://www.labvantage.com/informatics/analytics/" : "https://www.tcgdigital.com/industries/life-sciences/"} target="_blank" rel="noreferrer" className="p-text-link">Explore {platforms ? "LabVantage Analytics" : "industry solutions"} <Icon name="diagonal" size={17}/></a></div><div className="p-molecule" aria-hidden="true"><span /><span /><span /><span /><span /><i /><i /><i /></div></article>
        </div>
        <div className="p-product-note"><Icon name="spark" size={16}/><span>Your expertise brings the technology to life. Let’s create value together.</span></div>
      </div></section>;
    }
    function Levels({ detailed = false }) {
        const [compare, setCompare] = useState(detailed);
        return <section className="p-section p-container" id={id("levels")}>
        <SectionHeading eyebrow="A PARTNERSHIP THAT FITS" title="Different paths. Shared potential." description="Choose how you want to grow with TCG. We’ll build from there.">
          {!detailed && <Link className="p-text-link" to="/partner-levels">Explore partnership paths <Icon size={17}/></Link>}
        </SectionHeading>
        <div className="p-level-grid">{partnerPaths.map((path, i) => <article key={path.code} className={`p-level-card ${i === 1 ? "p-level-featured" : ""}`}>
          <div className="p-level-top"><span className="p-icon-tile"><Icon name={path.icon} size={24}/></span><span className="p-level-index">PATH 0{i + 1}</span></div>
          <h3>{path.name}</h3><p>{path.description}</p><div className="p-level-divider"/><span className="p-mini-label">YOUR OPPORTUNITY</span>
          <ul>{path.benefits.map(benefit => <li key={benefit}><Icon name="check" size={16}/>{benefit}</li>)}</ul>
          {detailed && <div className="p-level-detail"><h4>Who it’s for</h4><p>{path.audience}</p><h4>What you’ll need</h4><p>{path.requirements}</p><h4>Commercial benefit</h4><p>{path.incentive}</p></div>}
          <Link className={`p-button ${i === 1 ? "" : "p-button-outline"}`} to={`/register?type=${path.code}`}>Become a {i === 2 ? "partner" : path.name.split(" ")[0]?.toLowerCase() + " partner"}<Icon size={16}/></Link>
        </article>)}</div>
        <div className="p-level-footnote"><span>Built around your business. Benefits and terms are agreed with TCG.</span><button className="p-text-link" aria-expanded={compare} aria-controls={id("partner-comparison")} onClick={() => setCompare(!compare)}>{compare ? "Hide comparison" : "Compare partnership paths"} <Icon name="chevron" size={16} style={{ transform: compare ? "rotate(180deg)" : undefined }}/></button></div>
        {compare && <div className="p-comparison" id={id("partner-comparison")} tabIndex={0} role="region" aria-label="Partnership comparison"><table><caption>Find the right way to work together</caption><thead><tr><th scope="col">Your role & benefits</th>{partnerPaths.map(p => <th scope="col" key={p.code}>{p.name}</th>)}</tr></thead><tbody>
          <tr><th scope="row">Primary focus</th><td>Introduce qualified opportunities</td><td>Sell solutions to your customers</td><td>Integrate and implement solutions</td></tr>
          <tr><th scope="row">Customer sales lead</th><td>TCG</td><td>Your organization</td><td>Agreed per project</td></tr>
          <tr><th scope="row">Delivery responsibility</th><td>TCG</td><td>Agreed scope</td><td>Agreed implementation scope</td></tr>
          <tr><th scope="row">Commercial opportunity</th><td>Eligible referral commission</td><td>Customer-to-wholesale margin</td><td>Agreed project allocation</td></tr>
          <tr><th scope="row">Partner workspace</th>{partnerPaths.map(p => <td key={p.code}><Icon name="check" size={16}/> After approval</td>)}</tr>
          <tr><th scope="row">Eligibility</th><td>Relevant business network</td><td>Enterprise sales capability</td><td>Implementation expertise</td></tr>
        </tbody></table></div>}
      </section>;
    }
    function Testimonials({ expanded = false }) {
        const [index, setIndex] = useState(0);
        const [showDetail, setShowDetail] = useState(false);
        const story = stories[index];
        const changeStory = (next) => { setIndex((next + stories.length) % stories.length); setShowDetail(false); };
        return <section className="p-stories p-section"><div className="p-container">
        <SectionHeading eyebrow="GREAT THINGS HAPPEN TOGETHER" title="Shared vision. Meaningful impact." description="A look at what a TCG partnership can make possible.">
          {!expanded && <Link className="p-text-link" to="/partner-stories">Discover partner stories <Icon size={17}/></Link>}
        </SectionHeading>
        <div className="p-testimonial-card">
          <div className="p-testimonial-art"><span className="p-pill">PARTNER PERSPECTIVES</span><div className="p-story-sculpture" aria-hidden="true"><span /><span /><span /></div><div className="p-story-metric"><strong>{story.metric}</strong><span>{story.metricLabel}</span></div></div>
          <div className="p-testimonial-copy"><div className="p-story-meta"><span>{story.type}</span><span className="p-demo-badge">Illustrative story</span></div><span className="p-quote-mark" aria-hidden="true">“</span><blockquote key={index}>{story.quote}</blockquote><div className="p-story-person"><span className="p-person-avatar">{story.initials}</span><div><strong>{story.person}</strong><span>{story.role}, {story.company}</span></div></div>
            <div className="p-story-bottom"><button className="p-text-link" aria-expanded={showDetail} aria-controls={id("story-detail")} onClick={() => setShowDetail(!showDetail)}>{showDetail ? "Close story" : "Explore the story"} <Icon size={16}/></button><div className="p-carousel-controls"><span aria-live="polite">0{index + 1} <span>/ 0{stories.length}</span></span><button aria-label="Previous story" onClick={() => changeStory(index - 1)}><Icon style={{ transform: "rotate(180deg)" }} size={18}/></button><button aria-label="Next story" onClick={() => changeStory(index + 1)}><Icon size={18}/></button></div></div>
            {showDetail && <p className="p-story-detail" id={id("story-detail")}>{story.detail}</p>}
          </div>
        </div>
        <p className="p-content-note">Sample stories and names illustrate the partner experience; they are not actual endorsements or measured outcomes.</p>
        {expanded && <div className="p-story-selector">{stories.map((s, i) => <button key={s.company} aria-pressed={index === i} onClick={() => changeStory(i)}><span className="p-person-avatar">{s.initials}</span><span><strong>{s.company}</strong><small>{s.type}</small></span><Icon name="diagonal" size={17}/></button>)}</div>}
      </div></section>;
    }
    function HowItWorks() {
        return <section className="p-section p-container"><SectionHeading eyebrow="FROM HELLO TO WHAT’S NEXT" title="Your journey starts with a conversation."/><div className="p-steps-grid">{[
                ["01", "Find your fit", "Explore the partnership paths and choose the one that reflects your business."],
                ["02", "Introduce yourself", "Share your company details and tell us how you’d like to work with TCG."],
                ["03", "Align and get started", "Our team reviews your application and works with you on the next steps."],
            ].map(([number, title, text]) => <div key={number}><span className="p-step-number">{number}</span><h3>{title}</h3><p>{text}</p></div>)}</div></section>;
    }
    function Faq() {
        return <section className="p-section p-container p-faq"><div><span className="p-eyebrow">LET’S MAKE IT CLEAR</span><h2>A few things<br />you might be wondering.</h2><p>Still have a question? We’re here to help.</p><a className="p-text-link" href="mailto:contact@tcgdigital.com">Talk to our team <Icon size={17}/></a></div><div className="p-accordion">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<Icon name="plus" size={18}/></summary><p>{answer}</p></details>)}</div></section>;
    }
    function JoinCta() {
        return <section className="p-cta-wrap"><div className="p-container"><div className="p-cta"><div className="p-cta-rings" aria-hidden="true"/><div><span className="p-eyebrow">THE NEXT CHAPTER STARTS HERE</span><h2>Let’s build something<br /><em>extraordinary.</em></h2><p>Your expertise. Our technology. A world of possibility.</p></div><div className="p-cta-action"><Link to="/register" className="p-button">Become a partner <Icon size={18}/></Link><span>A shared ambition is all it takes to start.</span></div></div></div></section>;
    }

    function PageIntro({ eyebrow, title, text }) {
        return <div className="p-page-intro"><div className="p-container"><Link className="p-breadcrumb" to="/">Partner Network <span>/</span></Link><span className="p-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div></div>;
    }
    function HomePage() {
        return <>
        <section className="p-hero"><div className="p-container p-hero-grid">
          <div className="p-hero-copy"><span className="p-eyebrow"><span className="p-eyebrow-line"/> THE TCG PARTNER NETWORK</span><h1>Better together.<br />Built for <em>what’s next.</em></h1><p>Great partnerships turn possibility into progress.<br className="p-desktop-break"/> Bring your ambition. Build on our technology.<br className="p-desktop-break"/> Create lasting impact, together.</p><div className="p-hero-buttons"><Link to="/register" className="p-button">Become a partner <Icon size={18}/></Link><Link to="/partner-levels" className="p-button p-button-outline">Find your path <Icon name="diagonal" size={17}/></Link></div><div className="p-hero-note"><span className="p-overlap-icons"><span><Icon name="people" size={15}/></span><span><Icon name="code" size={15}/></span><span><Icon name="growth" size={15}/></span></span><span>Different strengths. <strong>One shared future.</strong></span></div></div>
          <NetworkArt />
        </div><div className="p-hero-bottom p-container"><span>INNOVATE WITH PURPOSE. GROW WITH CONFIDENCE.</span><Link to="/#benefits">Discover the possibilities <Icon size={15} style={{ transform: "rotate(90deg)" }}/></Link></div></section>
        <section className="p-ecosystem-strip"><div className="p-container"><p>Connected expertise.<br /><strong>The wider TCG ecosystem.</strong></p><a href="https://www.labvantage.com/" target="_blank" rel="noreferrer" className="p-ecosystem-logo p-labvantage">lab<span>vantage</span><span className="p-logo-dots" aria-hidden="true">⠿</span></a><a href="https://biomax.tcgdigital.com/" target="_blank" rel="noreferrer" className="p-ecosystem-logo p-biomax"><Icon name="network" size={28}/> biomax</a><a href="https://www.tcgls.com/" target="_blank" rel="noreferrer" className="p-ecosystem-logo p-lifesciences">TCG <span>LIFESCIENCES</span></a><span className="p-ecosystem-note">A shared spirit<br />of innovation.</span></div></section>
        <Benefits /><Products /><Levels /><Testimonials /><JoinCta />
      </>;
    }
    function PartnershipPage() {
        return <><PageIntro eyebrow="PARTNER WITH TCG" title="Together, we go further." text="TCG Digital brings enterprise AI, analytics, and industry expertise together. Our partner network connects that technology with businesses ready to create what’s next."/><Benefits extended/><section className="p-ecosystem-feature p-container"><div><span className="p-eyebrow">BUILT ON CONNECTION</span><h2>An ecosystem with<br />room for your ambition.</h2><p>Introduce an opportunity. Bring a solution to market. Deliver the next transformation. Our partner paths connect different strengths around a common goal: customer success.</p><Link className="p-text-link" to="/partner-levels">Find your place in the network <Icon size={18}/></Link></div><div className="p-ecosystem-diagram"><span className="p-ecosystem-center">TCG<small>PARTNER NETWORK</small></span><span>Referral partners</span><span>Reseller partners</span><span>System integrators</span></div></section><HowItWorks /><Faq /><JoinCta /></>;
    }
    function LevelsPage() {
        return <><PageIntro eyebrow="CHOOSE YOUR PARTNERSHIP PATH" title="Your business. Your path forward." text="Three ways to build with TCG. Explore each partnership type, compare responsibilities and benefits, and find the fit for your ambitions."/><Levels detailed/><Faq /><JoinCta /></>;
    }
    function StoriesPage() {
        return <><PageIntro eyebrow="PARTNER TESTIMONIALS & STORIES" title="Success is better when it’s shared." text="Discover the possibilities when relationships, expertise, and intelligent technology come together."/><Testimonials expanded/><section className="p-container p-section p-proof-section"><span className="p-eyebrow">EXPLORE REAL-WORLD TECHNOLOGY</span><h2>See the solutions behind the possibilities.</h2><p>Explore published capabilities and industry applications from TCG Digital and LabVantage.</p><div><a className="p-button p-button-outline" href="https://www.tcgdigital.com/industries/life-sciences/" target="_blank" rel="noreferrer">TCG life sciences <Icon name="diagonal" size={16}/></a><a className="p-button p-button-outline" href="https://www.labvantage.com/informatics/analytics/" target="_blank" rel="noreferrer">LabVantage Analytics <Icon name="diagonal" size={16}/></a></div></section><JoinCta /></>;
    }

    function JoinPage() {
        const isVisible = useLocation().pathname === "/register";
        const [additional, setAdditional] = useState([]);
        const [params] = useSearchParams();
        const initialType = partnerPaths.some(p => p.code === params.get("type")) ? params.get("type") : "";
        const [step, setStep] = useState(0);
        const [values, setValues] = useState({ company_name: "", company_email: "", website: "", country: "", partner_type_code: initialType, primary_contact_name: "", primary_contact_email: "", primary_contact_phone: "", password: "", confirm_password: "" });
        const [consent, setConsent] = useState(false);
        const [showPassword, setShowPassword] = useState(false);
        const heading = useRef(null);
        const confirmation = useRef(null);
        useEffect(() => {
            confirmation.current?.setCustomValidity(values.confirm_password === values.password ? "" : "Your passwords do not match.");
        }, [values.password, values.confirm_password, step]);
        const options = useRegistrationOptions();
        const mutation = useApplicationSubmission();
        const update = (name, value) => setValues(v => ({ ...v, [name]: value }));
        useEffect(() => { if (isVisible && step > 0)
            heading.current?.focus(); }, [step, isVisible]);
        useEffect(() => { if (isVisible && mutation.isSuccess)
            heading.current?.focus(); }, [mutation.isSuccess, isVisible]);
        const form = useRef(null);
        useEffect(() => {
            const requested = params.get("type");
            if (partnerPaths.some(path => path.code === requested)) {
                setValues(previous => ({ ...previous, partner_type_code: requested }));
            }
        }, [params.toString()]);
        useEffect(() => {
            if (isVisible && mutation.error)
                form.current?.querySelector('[role="alert"]')?.focus();
        }, [mutation.error, isVisible]);
        useEffect(() => {
            if (mutation.isSuccess) {
                setValues(previous => ({ ...previous, password: "", confirm_password: "" }));
                setShowPassword(false);
            }
        }, [mutation.isSuccess]);
        function next(event) {
            event.preventDefault();
            if (mutation.isPending)
                return;
            if (step === 0 && values.company_name.trim().length < 2) {
                const input = form.current?.querySelector('[name="company_name"]');
                input?.setCustomValidity("Enter a company name with at least two characters.");
                input?.reportValidity();
                return;
            }
            if (step === 1 && values.primary_contact_name.trim().length < 2) {
                const input = form.current?.querySelector('[name="primary_contact_name"]');
                input?.setCustomValidity("Enter a contact name with at least two characters.");
                input?.reportValidity();
                return;
            }
            if (step < 2) {
                mutation.clearError();
                setStep(step + 1);
                return;
            }
            if (!consent || mutation.isPending || !options.data)
                return;
            mutation.mutate({
                company_name: values.company_name.trim(),
                company_email: values.company_email.trim(),
                website: values.website.trim() || null,
                capability_codes: [...new Set([values.partner_type_code, ...additional])],
                country_codes: [values.country],
                primary_contact_name: values.primary_contact_name.trim(),
                primary_contact_email: values.primary_contact_email.trim(),
                primary_contact_phone: values.primary_contact_phone.trim() || null,
                password: values.password,
            });
        }
        if (mutation.isSuccess)
            return <section className="p-container p-join-success"><div className="p-success-icon"><Icon name="check" size={34}/></div><span className="p-eyebrow">YOUR NEXT CHAPTER IS UNDERWAY</span><h1 tabIndex={-1} ref={heading}>You’re one step closer.</h1><p>Thank you, {values.primary_contact_name}. We’ve received the application for <strong>{values.company_name}</strong>.</p><div className="p-reference"><span>APPLICATION REFERENCE</span><strong>{mutation.data.id.slice(0, 8).toUpperCase()}</strong><span className="p-pending-badge">Pending review</span></div><div className="p-next-steps"><h2>What happens next?</h2><ol><li><strong>We review your application.</strong><span>Our team checks your company details and partnership interests.</span></li><li><strong>We align on the opportunity.</strong><span>TCG may contact {values.primary_contact_email} to discuss the right path and terms.</span></li><li><strong>Your partnership begins.</strong><span>Workspace access is available after TCG approves your application.</span></li></ol></div><div className="p-hero-buttons"><Link to="/" className="p-button p-button-outline">Back to home</Link><Link to="/login" className="p-button">Partner sign in <Icon size={17}/></Link></div></section>;
        const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? "We couldn’t submit your application. Please try again. Your details are still here." : null;
        return <section className="p-join-page p-container">
        <div className="p-join-intro"><Link className="p-breadcrumb" to="/">Partner Network <span>/ Join now</span></Link><span className="p-eyebrow">LET’S GROW TOGETHER</span><h1>Great things start<br />with a hello.</h1><p>Tell us a little about your business.<br />We’ll explore what we can achieve together.</p><div className="p-join-promise"><span className="p-icon-tile"><Icon name="people"/></span><div><strong>A partnership built around you</strong><p>Our team reviews every application to find the right fit for your business.</p></div></div><div className="p-join-promise"><span className="p-icon-tile"><Icon name="shield"/></span><div><strong>A clear path forward</strong><p>Apply, connect with TCG, and get access to your workspace after approval.</p></div></div><div className="p-join-help">Already part of the network?<Link className="p-text-link" to="/login">Sign in to your workspace <Icon size={15}/></Link></div><span className="p-join-decoration" aria-hidden="true">together.</span></div>
        <div className="p-application">
          <ol className="p-form-progress" aria-label="Application progress">{["Company", "Your details", "Review"].map((label, i) => <li key={label} className={i <= step ? "is-active" : ""}><button disabled={i > step || mutation.isPending} onClick={() => setStep(i)} aria-current={step === i ? "step" : undefined}><span>{i < step ? <Icon name="check" size={14}/> : i + 1}</span>{label}</button></li>)}</ol>
          <form ref={form} className="p-join-form" onSubmit={next} aria-busy={mutation.isPending} onInput={event => { if (event.target instanceof HTMLInputElement && ["company_name", "primary_contact_name"].includes(event.target.name))
            event.target.setCustomValidity(""); }}>
            <span className="p-mini-label">STEP 0{step + 1} OF 03</span><h2 ref={heading} tabIndex={-1}>{["First, your company.", "Nice to meet you.", "Ready for what’s next?"][step]}</h2><p className="p-form-description">{["Introduce us to your business and choose your partnership path.", "You’ll be the primary contact and administrator for your company.", "Check your details before sending your application to TCG."][step]}</p>
            {options.isLoading && <p className="p-form-loading" role="status">Loading partnership options…</p>}{options.isError && <div className="p-form-error" role="alert">We couldn’t load the available partnership types and countries. Please try again.<button type="button" onClick={() => void options.refetch()} disabled={options.isFetching}>{options.isFetching ? "Retrying…" : "Retry loading options"}</button></div>}
            {step === 0 && <div className="p-form-fields">
              <label>Company name <span>*</span><input name="company_name" autoComplete="organization" placeholder="Your company name" required minLength={2} maxLength={200} value={values.company_name} onChange={e => update("company_name", e.target.value)}/></label>
              <label>Company email <span>*</span><input name="company_email" type="email" autoComplete="email" placeholder="hello@company.com" required value={values.company_email} onChange={e => update("company_email", e.target.value)}/></label>
              <label>Company website <small>Optional</small><input name="website" type="url" placeholder="https://yourcompany.com" value={values.website} onChange={e => update("website", e.target.value)}/></label>
              <label>Country / region <span>*</span><select name="country" autoComplete="country" value={values.country} onChange={e => update("country", e.target.value)} required disabled={!options.data}><option value="">{options.isLoading ? "Loading countries…" : "Select your country"}</option>{options.data?.countries.map(country => <option key={country.code} value={country.code}>{country.name}</option>)}</select></label>
              <label className="p-field-wide">How would you like to partner? <span>*</span><select name="partner_type_code" required value={values.partner_type_code} onChange={e => update("partner_type_code", e.target.value)} disabled={!options.data}><option value="">Select a partnership path</option>{options.data?.partner_types.map(type => <option key={type.code} value={type.code}>{type.name}</option>)}</select><small>Not sure? <Link to="/partner-levels">Compare the partnership paths <Icon name="diagonal" size={11}/></Link></small></label>
            </div>}
            {step === 0 && <fieldset className="p-capabilities"><legend>Additional capabilities (optional)</legend>{options.data?.partner_types.filter(item => item.code !== values.partner_type_code).map(item => <label className="p-consent" key={item.id}><input type="checkbox" checked={additional.includes(item.code)} onChange={e => setAdditional(e.target.checked ? [...additional, item.code] : additional.filter(code => code !== item.code))}/>{item.name}</label>)}</fieldset>}
            {step === 1 && <div className="p-form-fields">
              <label className="p-field-wide">Full name <span>*</span><input name="primary_contact_name" autoComplete="name" placeholder="First and last name" required minLength={2} maxLength={200} value={values.primary_contact_name} onChange={e => update("primary_contact_name", e.target.value)}/></label>
              <label className="p-field-wide">Work email <span>*</span><input name="primary_contact_email" type="email" autoComplete="username" placeholder="you@company.com" required value={values.primary_contact_email} onChange={e => update("primary_contact_email", e.target.value)}/><small>You’ll use this email to sign in after approval.</small></label>
              <label className="p-field-wide">Phone number <small>Optional</small><input name="primary_contact_phone" type="tel" autoComplete="tel" placeholder="+1 555 000 0000" maxLength={50} value={values.primary_contact_phone} onChange={e => update("primary_contact_phone", e.target.value)}/></label>
              <label className="p-field-wide">Create a password <span>*</span><span className="p-password-field"><input name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={12} maxLength={128} value={values.password} onChange={e => update("password", e.target.value)} aria-describedby={id("password-help")}/><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Hide" : "Show"}</button></span><small id={id("password-help")}>Use at least 12 characters.</small></label>
              <label className="p-field-wide">Confirm password <span>*</span><input ref={confirmation} name="confirm_password" type="password" autoComplete="new-password" required value={values.confirm_password} onChange={e => { update("confirm_password", e.target.value); e.target.setCustomValidity(e.target.value === values.password ? "" : "Your passwords don’t match."); }} onFocus={e => e.target.setCustomValidity(e.target.value === values.password ? "" : "Your passwords don’t match.")}/></label>
            </div>}
            {step === 2 && <div className="p-review"><div className="p-review-heading"><h3>Company information</h3><button type="button" disabled={mutation.isPending} onClick={() => setStep(0)}>Edit</button></div><dl><dt>Company</dt><dd>{values.company_name}</dd><dt>Company email</dt><dd>{values.company_email}</dd><dt>Country / region</dt><dd>{options.data?.countries.find(c => c.code === values.country)?.name}</dd><dt>Partnership</dt><dd>{options.data?.partner_types.filter(t => t.code === values.partner_type_code || additional.includes(t.code)).map(t => t.name).join(", ")}</dd>{values.website && <><dt>Website</dt><dd>{values.website}</dd></>}</dl><div className="p-review-heading"><h3>Primary contact</h3><button type="button" disabled={mutation.isPending} onClick={() => setStep(1)}>Edit</button></div><dl><dt>Name</dt><dd>{values.primary_contact_name}</dd><dt>Email</dt><dd>{values.primary_contact_email}</dd>{values.primary_contact_phone && <><dt>Phone</dt><dd>{values.primary_contact_phone}</dd></>}</dl><label className="p-consent"><input type="checkbox" required disabled={mutation.isPending} checked={consent} onChange={e => setConsent(e.target.checked)}/><span>I am authorized to apply on behalf of my company and agree that TCG may contact me about this application.</span></label></div>}
            {error && <div className="p-form-error" role="alert" tabIndex={-1}>{error}</div>}
            <div className="p-form-actions">{step > 0 && <button type="button" className="p-button p-button-outline" onClick={() => setStep(step - 1)} disabled={mutation.isPending}><Icon size={16} style={{ transform: "rotate(180deg)" }}/>Back</button>}<button type="submit" className="p-button" disabled={mutation.isPending || !options.data || options.isError}>{mutation.isPending ? "Submitting application…" : step === 2 ? "Submit application" : "Continue"}<Icon size={17}/></button></div>
            <p className="p-form-footnote"><Icon name="lock" size={13}/>Your details are used to review your partner application.</p>
          </form>
        </div>
      </section>;
    }

    const links = [
        ["/partner-with-tcg", "Partner with TCG"],
        ["/partner-levels", "Partnership paths"],
        ["/partner-stories", "Partner testimonials"],
    ];
    function PublicLayout() {
        const [menuOpen, setMenuOpen] = useState(false);
        const location = useLocation();
        const main = useRef(null);
        const menuToggle = useRef(null);
        useEffect(() => {
            setMenuOpen(false);
            const frame = requestAnimationFrame(() => {
                const target = location.hash ? rootRef.current?.querySelector('[id="' + id(location.hash.slice(1)) + '"]') : main.current?.querySelector('h1');
                if (target && (location.sequence > 0 || location.hash)) {
                    target.setAttribute("tabindex", "-1");
                    target.focus({ preventScroll: true });
                    if (location.sequence > 0 || location.hash)
                        target.scrollIntoView({ block: "start", behavior: "instant" });
                }
            });
            return () => cancelAnimationFrame(frame);
        }, [location.sequence]);
        return <div className="portal" data-tcg-portal="" ref={rootRef}>
        <style>{PORTAL_STYLES}</style>{settings.loadFonts && <link rel="stylesheet" href={settings.fontStylesheetUrl}/>}<a className="p-skip" href={"#" + id("main-content")} onClick={event => { event.preventDefault(); main.current?.focus(); main.current?.scrollIntoView({ block: "start" }); }}>Skip to content</a>
        <div className="p-announcement"><span>A shared vision. A world of possibilities.</span><Link to="/partner-with-tcg">Meet the TCG Partner Network <Icon size={14}/></Link></div>
        <header className="p-header">
          <div className="p-container p-header-inner">
            <Link to="/" className="p-brand" aria-label="TCG Digital Partner Network home" onClick={() => setMenuOpen(false)}><TcgMark /><span className="p-wordmark">TCG<span>digital</span></span><span className="p-brand-divider"/><span className="p-brand-label">PARTNER<br />NETWORK</span></Link>
            <nav aria-label="Main navigation" id={id("portal-navigation")} className={`p-nav ${menuOpen ? "is-open" : ""}`} onKeyDown={(event) => { if (event.key === "Escape") {
            setMenuOpen(false);
            menuToggle.current?.focus();
        } }}>
              {links.map(([to, text]) => <NavLink key={to} to={to} onClick={() => setMenuOpen(false)}>{text}</NavLink>)}
              <Link to="/login" className="p-login" onClick={() => setMenuOpen(false)}>Partner login <Icon name="diagonal" size={14}/></Link>
              <Link to="/register" className="p-button p-button-small" onClick={() => setMenuOpen(false)}>Join now <Icon size={16}/></Link>
            </nav>
            <button ref={menuToggle} className="p-menu-toggle" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} aria-controls={id("portal-navigation")} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? "close" : "menu"}/></button>
          </div>
        </header>
        <main ref={main} id={id("main-content")} tabIndex={-1}><Outlet /></main>
        <footer className="p-footer"><div className="p-container">
          <div className="p-footer-top"><div><Link className="p-brand" to="/"><TcgMark /><span className="p-wordmark">TCG<span>digital</span></span></Link><p>Shared expertise. Lasting impact.<br />Let’s build what’s next, together.</p></div>
            <div><h3>Partner network</h3><Link to="/partner-with-tcg">Why partner with TCG</Link><Link to="/partner-levels">Find your partnership</Link><Link to="/partner-stories">Partner stories</Link></div>
            <div><h3>Explore</h3><Link to="/#solutions">Products & solutions</Link><a href="https://www.tcgdigital.com/about/" target="_blank" rel="noreferrer">About TCG Digital <Icon name="diagonal" size={12}/></a><Link to="/login">Partner workspace</Link></div>
            <div className="p-footer-contact"><h3>A conversation starts it all.</h3><a href="mailto:contact@tcgdigital.com">contact@tcgdigital.com <Icon name="diagonal" size={16}/></a><Link to="/register" className="p-text-link">Become a partner <Icon size={16}/></Link></div>
          </div>
          <div className="p-footer-bottom"><span>© {new Date().getFullYear()} TCG Digital. All rights reserved.</span><span><Icon name="globe" size={14}/> Connected globally. Growing together.</span></div>
        </div></footer>
      </div>;
    }

    function Outlet() {
      const { location, registrationVisited } = useContext(Navigation);
      const pages = { "/": HomePage, "/partner-with-tcg": PartnershipPage, "/partner-levels": LevelsPage, "/partner-stories": StoriesPage };
      const Page = pages[location.pathname];
      return <>
        {Page && <Page key={location.pathname} />}
        {registrationVisited && <div hidden={location.pathname !== "/register"}><JoinPage /></div>}
      </>;
    }
    return function StandalonePortal() {
      const [location, setLocation] = useState(() => parseLocation(settings.initialPath));
      const [registrationVisited, setRegistrationVisited] = useState(location.pathname === "/register");
      function navigate(destination) {
        const next = parseLocation(destination, location.sequence + 1);
        if (next.pathname === "/register") setRegistrationVisited(true);
        setLocation(next);
      }
      return <Navigation.Provider value={{ location, navigate, registrationVisited }}><PublicLayout /></Navigation.Provider>;
    };
  }, [settings, instanceId]);
  return <Portal />;
}

render(<EzComponent />);