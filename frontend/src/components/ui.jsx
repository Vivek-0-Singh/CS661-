import { motion } from "framer-motion";
import { AnimatedNumber } from "../fx/AnimatedNumber.jsx";

const panelVariants = {
  hidden: { opacity: 0, y: 16 },
  show: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  }),
};

/**
 * Card panel with a staggered entrance (via `index`) and an optional state
 * ring: glow="ok" | "warn" | "crit". Animates on mount (the whole dashboard
 * fits one screen, so scroll-triggered reveals are unnecessary).
 */
export function Panel({ title, subtitle, actions, className = "", glow, index = 0, children }) {
  return (
    <motion.section
      className={`panel ${className}`}
      data-glow={glow}
      custom={index}
      variants={panelVariants}
      initial="hidden"
      animate="show"
    >
      <header className="panel-head">
        <div className="panel-title">
          <h3>{title}</h3>
          {subtitle && <span className="panel-sub">{subtitle}</span>}
        </div>
        {actions && <div className="panel-actions">{actions}</div>}
      </header>
      <div className="panel-body">{children}</div>
    </motion.section>
  );
}

export function Status({ loading, error, empty, children }) {
  if (error) return <div className="status err">⚠ {error}</div>;
  if (loading) return <div className="status">Loading…</div>;
  if (empty) return <div className="status">No data in range</div>;
  return children;
}

/**
 * Stat readout. Pass `num` (raw number) + `format` to get a spring-animated
 * counter; otherwise `value` renders as plain text.
 */
export function Stat({ label, value, num, format, tone }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      {format ? (
        <AnimatedNumber value={num} format={format} className={`stat-value ${tone ?? ""}`} />
      ) : (
        <span className={`stat-value ${tone ?? ""}`}>{value}</span>
      )}
    </div>
  );
}
