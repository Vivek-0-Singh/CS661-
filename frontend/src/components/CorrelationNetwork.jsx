import { useApp } from "../state.jsx";
import { COLORS, ASSET_COLOR } from "../theme";

/**
 * View 5, network mode — the correlation matrix as a 2D node-link diagram.
 * Nodes are assets (click one to make it the active asset); edge width and
 * opacity encode |ρ|, colour encodes sign (blue +, red −). Clicking an edge
 * drives the rolling-ρ drill-down below. Deliberately 2D: the data has no
 * third dimension, so the layout adds none (no occlusion, no perspective
 * distortion of edge lengths).
 */
const W = 440;
const H = 172;
const CX = W / 2;
const CY = H / 2 + 6;
const RX = 150;
const RY = 56;

export default function CorrelationNetwork({ matrix, labels }) {
  const { asset, setAsset, pair, setPair } = useApp();

  const nodes = labels.map((sym, i) => {
    const t = (i / labels.length) * 2 * Math.PI - Math.PI / 2;
    return { sym, x: CX + Math.cos(t) * RX, y: CY + Math.sin(t) * RY, angle: t };
  });

  const isSelected = (a, b) =>
    pair && ((pair[0] === a && pair[1] === b) || (pair[0] === b && pair[1] === a));

  const edges = [];
  nodes.forEach((a, i) =>
    nodes.slice(i + 1).forEach((b, jOff) => {
      const rho = matrix[i]?.[i + 1 + jOff];
      if (rho == null) return;
      edges.push({ a, b, rho, selected: isSelected(a.sym, b.sym) });
    })
  );

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", display: "block" }}
        role="img"
        aria-label="Correlation network: edge thickness shows correlation strength"
      >
        {/* Edges under nodes; selected edge drawn last so it stays on top. */}
        {edges
          .sort((e1, e2) => Number(e1.selected) - Number(e2.selected))
          .map(({ a, b, rho, selected }) => (
            <g
              key={`${a.sym}-${b.sym}`}
              style={{ cursor: "pointer" }}
              onClick={() => setPair([a.sym, b.sym])}
            >
              <title>{`${a.sym} · ${b.sym}  ρ = ${rho.toFixed(2)} — click to drill down`}</title>
              <line
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={rho >= 0 ? (selected ? "#0550ae" : COLORS.accent) : COLORS.bear}
                strokeWidth={(selected ? 2 : 0.6) + Math.abs(rho) * 4}
                strokeOpacity={selected ? 0.95 : 0.15 + Math.abs(rho) * 0.55}
                strokeLinecap="round"
              />
              {/* Invisible fat line so thin edges stay clickable. */}
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={12} />
            </g>
          ))}
        {nodes.map(({ sym, x, y, angle }) => {
          const active = sym === asset;
          const labelAbove = Math.sin(angle) < 0;
          return (
            <g key={sym} style={{ cursor: "pointer" }} onClick={() => setAsset(sym)}>
              <title>{`${sym} — click to make it the active asset`}</title>
              <circle
                cx={x} cy={y} r={active ? 11 : 8}
                fill={ASSET_COLOR[sym]}
                stroke={active ? COLORS.text : "#ffffff"}
                strokeWidth={active ? 2 : 1.5}
              />
              <text
                x={x}
                y={labelAbove ? y - 16 : y + 24}
                textAnchor="middle"
                fontSize={10.5}
                fontWeight={active ? 700 : 600}
                fill={COLORS.text}
              >
                {sym}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ color: COLORS.muted, fontSize: 10, textAlign: "center", marginTop: 2 }}>
        edge width = |ρ| · <span style={{ color: COLORS.accent }}>blue +</span> /{" "}
        <span style={{ color: COLORS.bear }}>red −</span> · click an edge to drill down, a node to
        switch asset
      </div>
    </div>
  );
}
