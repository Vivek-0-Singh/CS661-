import { useEffect, useRef } from "react";
import { animate } from "framer-motion";

/**
 * Tweened numeric readout: counts from the previous value to `value` whenever
 * it changes. Writes straight to the DOM node (no re-render per frame).
 * Renders `fallback` when value is null/undefined.
 */
export function AnimatedNumber({ value, format = (v) => v.toFixed(2), fallback = "—", className = "" }) {
  const ref = useRef(null);
  const prev = useRef(0);

  useEffect(() => {
    if (value == null || !Number.isFinite(value)) return;
    const controls = animate(prev.current, value, {
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        if (ref.current) ref.current.textContent = format(v);
      },
    });
    prev.current = value;
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  if (value == null || !Number.isFinite(value)) {
    return <span className={className}>{fallback}</span>;
  }
  return (
    <span ref={ref} className={className}>
      {format(prev.current)}
    </span>
  );
}
