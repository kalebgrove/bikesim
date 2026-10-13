// Display formatting — the only place SI values are converted for humans.

export function fmtClock(s: number): string {
  if (!isFinite(s)) return "--:--";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(sec).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function fmtDuration(s: number): string {
  if (!isFinite(s)) return "--";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0 ? `${h}h ${m}m ${sec}s` : `${m}m ${sec}s`;
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function fixed(n: number | undefined | null, decimals = 1): string {
  return n != null && isFinite(n) ? n.toFixed(decimals) : "--";
}
