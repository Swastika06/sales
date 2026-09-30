import { Link } from "react-router-dom";
import { useEffect } from "react";
import { Icon } from "./Icons";
import { NetworkArt } from "./NetworkArt";
import { Benefits, Faq, HowItWorks, JoinCta, Levels, Products, Testimonials } from "./PortalSections";

function PageIntro({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return <div className="p-page-intro"><div className="p-container"><Link className="p-breadcrumb" to="/">Partner Network <span>/</span></Link><span className="p-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div></div>;
}
export function HomePage() {
  useEffect(() => {
    if (window.location.hash === "#solutions") document.getElementById("solutions")?.scrollIntoView();
  }, []);
  return <>
    <section className="p-hero"><div className="p-container p-hero-grid">
      <div className="p-hero-copy"><span className="p-eyebrow"><span className="p-eyebrow-line" /> THE TCG PARTNER NETWORK</span><h1>Better together.<br />Built for <em>what’s next.</em></h1><p>Great partnerships turn possibility into progress.<br className="p-desktop-break" /> Bring your ambition. Build on our technology.<br className="p-desktop-break" /> Create lasting impact, together.</p><div className="p-hero-buttons"><Link to="/register" className="p-button">Become a partner <Icon size={18} /></Link><Link to="/partner-levels" className="p-button p-button-outline">Find your path <Icon name="diagonal" size={17} /></Link></div><div className="p-hero-note"><span className="p-overlap-icons"><span><Icon name="people" size={15} /></span><span><Icon name="code" size={15} /></span><span><Icon name="growth" size={15} /></span></span><span>Different strengths. <strong>One shared future.</strong></span></div></div>
      <NetworkArt />
    </div><div className="p-hero-bottom p-container"><span>INNOVATE WITH PURPOSE. GROW WITH CONFIDENCE.</span><a href="#benefits">Discover the possibilities <Icon size={15} style={{ transform: "rotate(90deg)" }} /></a></div></section>
    <section className="p-ecosystem-strip"><div className="p-container"><p>Connected expertise.<br /><strong>The wider TCG ecosystem.</strong></p><a href="https://www.labvantage.com/" target="_blank" rel="noreferrer" className="p-ecosystem-logo p-labvantage">lab<span>vantage</span><span className="p-logo-dots" aria-hidden="true">⠿</span></a><a href="https://biomax.tcgdigital.com/" target="_blank" rel="noreferrer" className="p-ecosystem-logo p-biomax"><Icon name="network" size={28} /> biomax</a><a href="https://www.tcgls.com/" target="_blank" rel="noreferrer" className="p-ecosystem-logo p-lifesciences">TCG <span>LIFESCIENCES</span></a><span className="p-ecosystem-note">A shared spirit<br />of innovation.</span></div></section>
    <Benefits /><Products /><Levels /><Testimonials /><JoinCta />
  </>;
}
export function PartnershipPage() {
  return <><PageIntro eyebrow="PARTNER WITH TCG" title="Together, we go further." text="TCG Digital brings enterprise AI, analytics, and industry expertise together. Our partner network connects that technology with businesses ready to create what’s next." /><Benefits extended /><section className="p-ecosystem-feature p-container"><div><span className="p-eyebrow">BUILT ON CONNECTION</span><h2>An ecosystem with<br />room for your ambition.</h2><p>Introduce an opportunity. Bring a solution to market. Deliver the next transformation. Our partner paths connect different strengths around a common goal: customer success.</p><Link className="p-text-link" to="/partner-levels">Find your place in the network <Icon size={18} /></Link></div><div className="p-ecosystem-diagram"><span className="p-ecosystem-center">TCG<small>PARTNER NETWORK</small></span><span>Referral partners</span><span>Reseller partners</span><span>System integrators</span></div></section><HowItWorks /><Faq /><JoinCta /></>;
}
export function LevelsPage() {
  return <><PageIntro eyebrow="CHOOSE YOUR LEVEL OF ENGAGEMENT" title="Your business. Your path forward." text="Three ways to build with TCG. Explore each partnership type, compare responsibilities and benefits, and find the fit for your ambitions." /><Levels detailed /><Faq /><JoinCta /></>;
}
export function StoriesPage() {
  return <><PageIntro eyebrow="PARTNER TESTIMONIALS & STORIES" title="Success is better when it’s shared." text="Discover the possibilities when relationships, expertise, and intelligent technology come together." /><Testimonials expanded /><section className="p-container p-section p-proof-section"><span className="p-eyebrow">EXPLORE REAL-WORLD TECHNOLOGY</span><h2>See the solutions behind the possibilities.</h2><p>Explore published capabilities and industry applications from TCG Digital and LabVantage.</p><div><a className="p-button p-button-outline" href="https://www.tcgdigital.com/industries/life-sciences/" target="_blank" rel="noreferrer">TCG life sciences <Icon name="diagonal" size={16} /></a><a className="p-button p-button-outline" href="https://www.labvantage.com/informatics/analytics/" target="_blank" rel="noreferrer">LabVantage Analytics <Icon name="diagonal" size={16} /></a></div></section><JoinCta /></>;
}

