import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icons";
import { benefits, faqs, partnerPaths, stories } from "./portalData";

export function SectionHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description?: string; children?: React.ReactNode }) {
  return <div className="p-section-heading"><div><span className="p-eyebrow">{eyebrow}</span><h2>{title}</h2>{description && <p>{description}</p>}</div>{children}</div>;
}
export function Benefits({ extended = false }: { extended?: boolean }) {
  return <section className="p-section p-container" id="benefits">
    <SectionHeading eyebrow="THE POWER OF PARTNERSHIP" title="Your ambition. Our shared advantage." description="More than a partnership. A foundation for what comes next.">
      {!extended && <Link className="p-text-link" to="/partner-with-tcg">Why partner with TCG <Icon size={17} /></Link>}
    </SectionHeading>
    <div className="p-benefit-grid">{benefits.map((benefit, i) => <article className="p-benefit-card" key={benefit.title}><div className="p-benefit-top"><span className="p-icon-tile"><Icon name={benefit.icon} size={24} /></span><span className="p-card-number">0{i + 1}</span></div><h3>{benefit.title}</h3><p>{benefit.text}</p></article>)}</div>
    {extended && <div className="p-benefit-extras"><div><Icon name="book" /><h3>Knowledge that moves you forward</h3><p>Align your team on product knowledge, solution design, and the resources available within your partnership.</p></div><div><Icon name="shield" /><h3>A workspace for your business</h3><p>Manage authorized opportunities and access the information your team needs through the partner portal.</p></div><div><Icon name="network" /><h3>A connected ecosystem</h3><p>Collaborate across technology, industry, and delivery disciplines to create meaningful customer outcomes.</p></div></div>}
  </section>;
}
export function Products() {
  const [active, setActive] = useState("Platforms");
  const platforms = active === "Platforms";
  return <section className="p-solutions p-section" id="solutions"><div className="p-container">
    <SectionHeading eyebrow="INNOVATION YOU CAN BUILD ON" title="Powerful platforms. Real-world possibilities." description="Bring intelligent solutions to the businesses that need them.">
      <div className="p-tabs" aria-label="Solution category">{["Platforms", "Services"].map(tab => <button key={tab} aria-pressed={active === tab} onClick={() => setActive(tab)}>{tab}</button>)}</div>
    </SectionHeading>
    <div className="p-product-grid" key={active}>
      <article className="p-product-card p-product-mcube"><div className="p-product-copy"><span className="p-pill">{platforms ? "ENTERPRISE AI & ANALYTICS" : "DATA & AI SERVICES"}</span><h3>{platforms ? <>m<span className="p-cube-name">cube</span><sup>™</sup></> : "Intelligence, applied."}</h3><p>{platforms ? "Turn enterprise data into decisions. An end-to-end AI and analytics platform that connects insights to business impact." : "Connect your data strategy to your business ambition with TCG’s enterprise AI and digital transformation expertise."}</p><a href={platforms ? "https://www.tcgdigital.com/tcg-mcube/" : "https://www.tcgdigital.com/"} target="_blank" rel="noreferrer" className="p-text-link">Explore {platforms ? "mcube" : "TCG services"} <Icon name="diagonal" size={17} /></a></div><div className="p-product-visual" aria-hidden="true"><div className="p-cube p-cube-one" /><div className="p-cube p-cube-two" /><div className="p-cube p-cube-three" /><div className="p-visual-cross">+</div></div></article>
      <article className="p-product-card p-product-lva"><div className="p-product-copy"><span className="p-pill">{platforms ? "LABORATORY INTELLIGENCE" : "INDUSTRY EXPERTISE"}</span><h3>{platforms ? <>LabVantage<span className="p-product-subtitle">Analytics</span></> : "Built around your industry."}</h3><p>{platforms ? "Make every discovery count. Bring self-service analytics, predictive insight, and AI to laboratory data." : "From life sciences to industrial operations, bring domain knowledge and intelligent platforms together."}</p><a href={platforms ? "https://www.labvantage.com/informatics/analytics/" : "https://www.tcgdigital.com/industries/life-sciences/"} target="_blank" rel="noreferrer" className="p-text-link">Explore {platforms ? "LabVantage Analytics" : "industry solutions"} <Icon name="diagonal" size={17} /></a></div><div className="p-molecule" aria-hidden="true"><span /><span /><span /><span /><span /><i /><i /><i /></div></article>
    </div>
    <div className="p-product-note"><Icon name="spark" size={16} /><span>Your expertise brings the technology to life. Let’s create value together.</span></div>
  </div></section>;
}
export function Levels({ detailed = false }: { detailed?: boolean }) {
  const [compare, setCompare] = useState(detailed);
  return <section className="p-section p-container" id="levels">
    <SectionHeading eyebrow="A PARTNERSHIP THAT FITS" title="Different paths. Shared potential." description="Choose how you want to grow with TCG. We’ll build from there.">
      {!detailed && <Link className="p-text-link" to="/partner-levels">Explore partner levels <Icon size={17} /></Link>}
    </SectionHeading>
    <div className="p-level-grid">{partnerPaths.map((path, i) => <article key={path.code} className={`p-level-card ${i === 1 ? "p-level-featured" : ""}`}>
      <div className="p-level-top"><span className="p-icon-tile"><Icon name={path.icon} size={24} /></span><span className="p-level-index">PATH 0{i + 1}</span></div>
      <h3>{path.name}</h3><p>{path.description}</p><div className="p-level-divider" /><span className="p-mini-label">YOUR OPPORTUNITY</span>
      <ul>{path.benefits.map(benefit => <li key={benefit}><Icon name="check" size={16} />{benefit}</li>)}</ul>
      {detailed && <div className="p-level-detail"><h4>Who it’s for</h4><p>{path.audience}</p><h4>What you’ll need</h4><p>{path.requirements}</p><h4>Commercial benefit</h4><p>{path.incentive}</p></div>}
      <Link className={`p-button ${i === 1 ? "" : "p-button-outline"}`} to={`/register?type=${path.code}`}>Become a {i === 2 ? "partner" : path.name.split(" ")[0]?.toLowerCase() + " partner"}<Icon size={16} /></Link>
    </article>)}</div>
    <div className="p-level-footnote"><span>Built around your business. Benefits and terms are agreed with TCG.</span><button className="p-text-link" aria-expanded={compare} aria-controls="partner-comparison" onClick={() => setCompare(!compare)}>{compare ? "Hide comparison" : "Compare partnership paths"} <Icon name="chevron" size={16} style={{ transform: compare ? "rotate(180deg)" : undefined }} /></button></div>
    {compare && <div className="p-comparison" id="partner-comparison" tabIndex={0} role="region" aria-label="Partnership comparison"><table><caption>Find the right way to work together</caption><thead><tr><th scope="col">Your role & benefits</th>{partnerPaths.map(p => <th scope="col" key={p.code}>{p.name}</th>)}</tr></thead><tbody>
      <tr><th scope="row">Primary focus</th><td>Introduce qualified opportunities</td><td>Sell solutions to your customers</td><td>Integrate and implement solutions</td></tr>
      <tr><th scope="row">Customer sales lead</th><td>TCG</td><td>Your organization</td><td>Agreed per project</td></tr>
      <tr><th scope="row">Delivery responsibility</th><td>TCG</td><td>Agreed scope</td><td>Agreed implementation scope</td></tr>
      <tr><th scope="row">Commercial opportunity</th><td>Eligible referral commission</td><td>Customer-to-wholesale margin</td><td>Agreed project allocation</td></tr>
      <tr><th scope="row">Partner workspace</th>{partnerPaths.map(p => <td key={p.code}><Icon name="check" size={16} /> After approval</td>)}</tr>
      <tr><th scope="row">Eligibility</th><td>Relevant business network</td><td>Enterprise sales capability</td><td>Implementation expertise</td></tr>
    </tbody></table></div>}
  </section>;
}
export function Testimonials({ expanded = false }: { expanded?: boolean }) {
  const [index, setIndex] = useState(0);
  const [showDetail, setShowDetail] = useState(false);
  const story = stories[index]!;
  const changeStory = (next: number) => { setIndex((next + stories.length) % stories.length); setShowDetail(false); };
  return <section className="p-stories p-section"><div className="p-container">
    <SectionHeading eyebrow="GREAT THINGS HAPPEN TOGETHER" title="Shared vision. Meaningful impact." description="A look at what a TCG partnership can make possible.">
      {!expanded && <Link className="p-text-link" to="/partner-stories">Discover partner stories <Icon size={17} /></Link>}
    </SectionHeading>
    <div className="p-testimonial-card">
      <div className="p-testimonial-art"><span className="p-pill">PARTNER PERSPECTIVES</span><div className="p-story-sculpture" aria-hidden="true"><span /><span /><span /></div><div className="p-story-metric"><strong>{story.metric}</strong><span>{story.metricLabel}</span></div></div>
      <div className="p-testimonial-copy"><div className="p-story-meta"><span>{story.type}</span><span className="p-demo-badge">Illustrative story</span></div><span className="p-quote-mark" aria-hidden="true">“</span><blockquote key={index}>{story.quote}</blockquote><div className="p-story-person"><span className="p-person-avatar">{story.initials}</span><div><strong>{story.person}</strong><span>{story.role}, {story.company}</span></div></div>
        <div className="p-story-bottom"><button className="p-text-link" aria-expanded={showDetail} onClick={() => setShowDetail(!showDetail)}>{showDetail ? "Close story" : "Explore the story"} <Icon size={16} /></button><div className="p-carousel-controls"><span aria-live="polite">0{index + 1} <span>/ 0{stories.length}</span></span><button aria-label="Previous story" onClick={() => changeStory(index - 1)}><Icon style={{ transform: "rotate(180deg)" }} size={18} /></button><button aria-label="Next story" onClick={() => changeStory(index + 1)}><Icon size={18} /></button></div></div>
        {showDetail && <p className="p-story-detail">{story.detail}</p>}
      </div>
    </div>
    <p className="p-content-note">Sample stories and names illustrate the partner experience; they are not actual endorsements or measured outcomes.</p>
    {expanded && <div className="p-story-selector">{stories.map((s, i) => <button key={s.company} aria-pressed={index === i} onClick={() => changeStory(i)}><span className="p-person-avatar">{s.initials}</span><span><strong>{s.company}</strong><small>{s.type}</small></span><Icon name="diagonal" size={17} /></button>)}</div>}
  </div></section>;
}
export function HowItWorks() {
  return <section className="p-section p-container"><SectionHeading eyebrow="FROM HELLO TO WHAT’S NEXT" title="Your journey starts with a conversation." /><div className="p-steps-grid">{[
    ["01", "Find your fit", "Explore the partnership paths and choose the one that reflects your business."],
    ["02", "Introduce yourself", "Share your company details and tell us how you’d like to work with TCG."],
    ["03", "Align and get started", "Our team reviews your application and works with you on the next steps."],
  ].map(([number, title, text]) => <div key={number}><span className="p-step-number">{number}</span><h3>{title}</h3><p>{text}</p></div>)}</div></section>;
}
export function Faq() {
  return <section className="p-section p-container p-faq"><div><span className="p-eyebrow">LET’S MAKE IT CLEAR</span><h2>A few things<br />you might be wondering.</h2><p>Still have a question? We’re here to help.</p><a className="p-text-link" href="mailto:contact@tcgdigital.com">Talk to our team <Icon size={17} /></a></div><div className="p-accordion">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<Icon name="plus" size={18} /></summary><p>{answer}</p></details>)}</div></section>;
}
export function JoinCta() {
  return <section className="p-cta-wrap"><div className="p-container"><div className="p-cta"><div className="p-cta-rings" aria-hidden="true" /><div><span className="p-eyebrow">THE NEXT CHAPTER STARTS HERE</span><h2>Let’s build something<br /><em>extraordinary.</em></h2><p>Your expertise. Our technology. A world of possibility.</p></div><div className="p-cta-action"><Link to="/register" className="p-button">Become a partner <Icon size={18} /></Link><span>A shared ambition is all it takes to start.</span></div></div></div></section>;
}

