import { useEffect, useRef } from "react";

const W = 120;
const H = 18;

/**
 * State-driven particle strip: every change in `mid` (live order-book mid
 * price) emits particles — green drifting up on an uptick, red drifting down
 * on a downtick. Cheap 2D canvas, no render loop when reduced motion is set.
 */
export function TickPulse({ mid }) {
  const canvasRef = useRef(null);
  const parts = useRef([]);
  const last = useRef(null);

  useEffect(() => {
    if (last.current != null && mid != null && mid !== last.current) {
      const d = mid - last.current;
      const n = Math.min(12, 3 + Math.ceil(Math.abs(d)));
      for (let i = 0; i < n; i++) {
        parts.current.push({
          x: 4,
          y: H / 2 + (Math.random() - 0.5) * 6,
          vx: 1.1 + Math.random() * 1.9,
          vy: (d > 0 ? -1 : 1) * (0.25 + Math.random() * 0.8),
          life: 1,
          c: d > 0 ? "26,127,55" : "207,34,46",
        });
      }
      if (parts.current.length > 240) parts.current.splice(0, parts.current.length - 240);
    }
    last.current = mid;
  }, [mid]);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = canvasRef.current.getContext("2d");
    let raf;
    const loop = () => {
      ctx.clearRect(0, 0, W, H);
      parts.current = parts.current.filter((p) => p.life > 0 && p.x < W);
      for (const p of parts.current) {
        p.x += p.vx;
        p.y += p.vy;
        p.life -= 0.028;
        ctx.fillStyle = `rgba(${p.c},${Math.max(p.life, 0)})`;
        ctx.fillRect(p.x, p.y, 2.5, 2.5);
      }
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={W}
      height={H}
      style={{ verticalAlign: "middle", marginRight: 6 }}
      aria-hidden
    />
  );
}
