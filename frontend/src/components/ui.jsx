export function Panel({ title, subtitle, actions, className = "", children }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <div className="panel-title">
          <h3>{title}</h3>
          {subtitle && <span className="panel-sub">{subtitle}</span>}
        </div>
        {actions && <div className="panel-actions">{actions}</div>}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function Status({ loading, error, empty, children }) {
  if (error) return <div className="status err">⚠ {error}</div>;
  if (loading) return <div className="status">Loading…</div>;
  if (empty) return <div className="status">No data in range</div>;
  return children;
}

export function Stat({ label, value, tone }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${tone ?? ""}`}>{value}</span>
    </div>
  );
}
