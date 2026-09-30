import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Icon, TcgLogo } from "./Icons";

const links = [
  ["/partner-with-tcg", "Partner with TCG"],
  ["/partner-levels", "Partnership paths"],
  ["/partner-stories", "Partner testimonials"],
];
export function PublicLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useEffect(() => {
    if (location.hash) {
      requestAnimationFrame(() => document.getElementById(location.hash.slice(1))?.scrollIntoView());
    } else window.scrollTo({ top: 0, behavior: "instant" });
    const titles: Record<string, string> = { "/": "Grow together", "/partner-with-tcg": "Partner with TCG", "/partner-levels": "Choose your partnership", "/partner-stories": "Partner stories", "/register": "Become a partner" };
    document.title = `${titles[location.pathname] ?? "Welcome"} | TCG Partner Network`;
  }, [location.pathname, location.hash]);
  return <div className="portal">
    <a className="p-skip" href="#main-content">Skip to content</a>
    <div className="p-announcement"><span>A shared vision. A world of possibilities.</span><Link to="/partner-with-tcg">Meet the TCG Partner Network <Icon size={14} /></Link></div>
    <header className="p-header">
      <div className="p-container p-header-inner">
        <Link to="/" className="p-brand" aria-label="TCG Digital Partner Network home" onClick={() => setMenuOpen(false)}><TcgLogo /><span className="p-brand-divider" /><span className="p-brand-label">PARTNER<br />NETWORK</span></Link>
        <nav aria-label="Main navigation" id="portal-navigation" className={`p-nav ${menuOpen ? "is-open" : ""}`} onKeyDown={(event) => { if (event.key === "Escape") setMenuOpen(false); }}>
          {links.map(([to, text]) => <NavLink key={to} to={to!} onClick={() => setMenuOpen(false)}>{text}</NavLink>)}
          <Link to="/login" className="p-login" onClick={() => setMenuOpen(false)}>Partner login <Icon name="diagonal" size={14} /></Link>
          <Link to="/register" className="p-button p-button-small" onClick={() => setMenuOpen(false)}>Join now <Icon size={16} /></Link>
        </nav>
        <button className="p-menu-toggle" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} aria-controls="portal-navigation" onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? "close" : "menu"} /></button>
      </div>
    </header>
    <main id="main-content"><Outlet /></main>
    <footer className="p-footer"><div className="p-container">
      <div className="p-footer-top"><div><Link className="p-brand" to="/"><TcgLogo /></Link><p>Shared expertise. Lasting impact.<br />Let’s build what’s next, together.</p></div>
        <div><h3>Partner network</h3><Link to="/partner-with-tcg">Why partner with TCG</Link><Link to="/partner-levels">Find your partnership</Link><Link to="/partner-stories">Partner stories</Link></div>
        <div><h3>Explore</h3><Link to="/#solutions">Products & solutions</Link><a href="https://www.tcgdigital.com/about/" target="_blank" rel="noreferrer">About TCG Digital <Icon name="diagonal" size={12} /></a><Link to="/login">Partner workspace</Link></div>
        <div className="p-footer-contact"><h3>A conversation starts it all.</h3><a href="mailto:contact@tcgdigital.com">contact@tcgdigital.com <Icon name="diagonal" size={16} /></a><Link to="/register" className="p-text-link">Become a partner <Icon size={16} /></Link></div>
      </div>
      <div className="p-footer-bottom"><span>© {new Date().getFullYear()} TCG Digital. All rights reserved.</span><span><Icon name="globe" size={14} /> Connected globally. Growing together.</span></div>
    </div></footer>
  </div>;
}

