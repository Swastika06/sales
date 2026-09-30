import { Icon } from "./Icons";

export function NetworkArt() {
  return <div className="p-network-art" role="img" aria-label="An interconnected globe representing TCG's partner ecosystem">
    <div className="p-art-grid" />
    <div className="p-art-orbit p-art-orbit-one" /><div className="p-art-orbit p-art-orbit-two" />
    <svg className="p-globe-art" viewBox="0 0 600 600" fill="none" aria-hidden="true">
      <defs>
        <radialGradient id="globe-fill" cx=".32" cy=".25" r=".85"><stop stopColor="#fffaf1" /><stop offset=".5" stopColor="#f7d3b3" /><stop offset="1" stopColor="#c65c2c" /></radialGradient>
        <linearGradient id="globe-lines" x1="140" y1="100" x2="460" y2="500" gradientUnits="userSpaceOnUse"><stop stopColor="#db793b" /><stop offset=".5" stopColor="#e8a579" /><stop offset="1" stopColor="#a04622" /></linearGradient>
        <linearGradient id="ribbon" x1="100" y1="100" x2="500" y2="460" gradientUnits="userSpaceOnUse"><stop stopColor="#fe9149" /><stop offset=".55" stopColor="#ed6b30" /><stop offset="1" stopColor="#bc411a" /></linearGradient>
        <filter id="globe-shadow"><feDropShadow dx="5" dy="24" stdDeviation="20" floodColor="#a75c31" floodOpacity=".16" /></filter>
        <clipPath id="globe-clip"><circle cx="300" cy="300" r="179" /></clipPath>
      </defs>
      <g filter="url(#globe-shadow)"><circle cx="300" cy="300" r="179" fill="url(#globe-fill)" />
        <g clipPath="url(#globe-clip)" stroke="url(#globe-lines)" strokeWidth=".8" opacity=".65" transform="rotate(-22 300 300)">
          {[32, 65, 100, 140, 177].map((rx) => <ellipse key={rx} cx="300" cy="300" rx={rx} ry="179" />)}
          {[145, 178, 216, 258, 300, 342, 384, 422, 455].map((cy) => <ellipse key={cy} cx="300" cy={cy} rx="184" ry="31" />)}
        </g>
      </g>
      <ellipse cx="300" cy="300" rx="249" ry="90" transform="rotate(-38 300 300)" stroke="#d57442" strokeWidth="1" strokeDasharray="4 6" opacity=".55" />
      <path d="M136 201C78 260 102 380 236 431c122 46 259 7 265-53" stroke="url(#ribbon)" strokeWidth="29" />
      <path d="M136 201C78 260 102 380 236 431c122 46 259 7 265-53" stroke="#ffb576" strokeWidth="1.5" transform="translate(0 -14)" opacity=".75" />
      <path d="M391 153c-84-75-243-48-295 39" stroke="url(#ribbon)" strokeWidth="13" />
      <g fill="#fff9f2" stroke="#cf6c34"><circle cx="178" cy="215" r="6" /><circle cx="402" cy="219" r="5" /><circle cx="333" cy="397" r="5" /><circle cx="261" cy="163" r="4" /><circle cx="458" cy="316" r="4" /></g>
      <g stroke="#ad6d4a" strokeDasharray="3 5" opacity=".7"><path d="m178 215 83-52 141 56-69 178-155-182 224 4 56 97-125 81" /></g>
    </svg>
    <div className="p-art-tag p-art-tag-top"><span className="p-icon-tile"><Icon name="network" /></span><span><small>ONE CONNECTED ECOSYSTEM</small><strong>More possibility. Together.</strong></span><span className="p-live-dot" /></div>
    <div className="p-art-tag p-art-tag-left"><Icon name="code" size={18} /><span>Build with confidence</span></div>
    <div className="p-art-tag p-art-tag-right"><span className="p-art-arrow"><Icon name="growth" size={21} /></span><span><small>SHARED AMBITION</small><strong>Limitless potential</strong></span></div>
    <span className="p-art-coordinate">CONNECTED BY EXPERTISE. UNITED BY POSSIBILITY.</span>
    <span className="p-art-plus p-art-plus-a">+</span><span className="p-art-plus p-art-plus-b">+</span>
  </div>;
}

