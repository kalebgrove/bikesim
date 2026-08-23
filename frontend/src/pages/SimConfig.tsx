import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { useRoute } from "../hooks/useStore";
import { useSimEngineContext } from "../lib/simEngineContext";
import type { SimConfig as SimConfigType } from "../lib/types";
import ElevationProfile from "../components/ElevationProfile";

interface FormState {
  // Rider
  mass: string;
  ftp: string;
  cda: string;
  crr: string;
  // Environment
  windSpeed: string;
  windBearing: string;
  temperature: string;
  // Strategy
  targetPower: string;
  // Sim settings
  timeStepS: string;
  tickIntervalMs: string;
}

function Field({
  label,
  name,
  value,
  onChange,
  unit,
  hint,
  min,
  max,
  step,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  unit?: string;
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          name={name}
          value={value}
          onChange={onChange}
          min={min}
          max={max}
          step={step ?? 1}
          className="w-full px-3 py-1.5 text-sm mono rounded border outline-none focus:ring-1"
          style={{
            background: "var(--secondary)",
            border: "1px solid var(--border)",
            color: "var(--foreground)",
            fontFamily: "var(--font-mono)",
          }}
        />
        {unit && (
          <span className="text-xs shrink-0 w-10 text-right" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            {unit}
          </span>
        )}
      </div>
      {hint && (
        <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
          {hint}
        </p>
      )}
    </div>
  );
}

function SectionHead({ title }: { title: string }) {
  return (
    <div className="pt-4 pb-2 border-b" style={{ borderColor: "var(--border)" }}>
      <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--primary)", fontFamily: "var(--font-mono)" }}>
        {title}
      </span>
    </div>
  );
}

export default function SimConfig() {
  const { routeId } = useParams<{ routeId: string }>();
  const route = useRoute(routeId);
  const { start } = useSimEngineContext();
  const navigate = useNavigate();

  const [form, setForm] = useState<FormState>({
    mass: "75",
    ftp: "300",
    cda: "0.32",
    crr: "0.004",
    windSpeed: "3",
    windBearing: "0",
    temperature: "18",
    targetPower: "250",
    timeStepS: "10",
    tickIntervalMs: "200",
  });
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  function validate(): boolean {
    const errs: Partial<Record<keyof FormState, string>> = {};
    const n = (k: keyof FormState) => parseFloat(form[k]);
    if (n("mass") < 40 || n("mass") > 150) errs.mass = "40–150 kg";
    if (n("ftp") < 50 || n("ftp") > 600) errs.ftp = "50–600 W";
    if (n("cda") < 0.1 || n("cda") > 0.8) errs.cda = "0.10–0.80 m²";
    if (n("crr") < 0.001 || n("crr") > 0.02) errs.crr = "0.001–0.020";
    if (n("windSpeed") < 0 || n("windSpeed") > 30) errs.windSpeed = "0–30 m/s";
    if (n("targetPower") < 50 || n("targetPower") > 700) errs.targetPower = "50–700 W";
    if (n("timeStepS") < 1 || n("timeStepS") > 60) errs.timeStepS = "1–60 s";
    if (n("tickIntervalMs") < 50 || n("tickIntervalMs") > 2000) errs.tickIntervalMs = "50–2000 ms";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate() || !routeId || !route || starting) return;

    const f = (k: keyof FormState) => parseFloat(form[k]);
    const config: SimConfigType = {
      routeId,
      rider: { mass: f("mass"), ftp: f("ftp"), cda: f("cda"), crr: f("crr") },
      environment: {
        windSpeed: f("windSpeed"),
        windBearing: f("windBearing"),
        temperature: f("temperature"),
        airDensity: 1.225 * Math.exp(-0.0001 * route.minElevation), // simplified altitude correction
      },
      strategy: { type: "constant_power", targetPower: f("targetPower") },
      simSettings: { timeStepS: f("timeStepS"), tickIntervalMs: f("tickIntervalMs") },
    };

    setStarting(true);
    setStartError(null);
    try {
      const simId = await start(config);
      navigate(`/simulations/${simId}/live`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not start simulation");
    } finally {
      setStarting(false);
    }
  }

  if (!route) {
    return (
      <div className="p-6 text-sm" style={{ color: "var(--muted-foreground)" }}>
        Route not found.{" "}
        <Link to="/upload" style={{ color: "var(--primary)" }}>Upload one →</Link>
      </div>
    );
  }

  const targetPowerW = parseFloat(form.targetPower) || 0;
  const ftpW = parseFloat(form.ftp) || 1;
  const pctFtp = isFinite(targetPowerW / ftpW) ? ((targetPowerW / ftpW) * 100).toFixed(0) : "--";

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <div className="flex items-start gap-6">
        {/* Config form */}
        <form onSubmit={handleSubmit} className="w-80 shrink-0 space-y-4">
          <div>
            <div className="text-xs mb-1" style={{ color: "var(--muted-foreground)" }}>
              <Link to="/" className="hover:underline">Dashboard</Link>
              {" / "}
              <Link to={`/routes/${routeId}`} className="hover:underline">Route</Link>
              {" / "}
              Configure
            </div>
            <h1 className="text-xl font-bold" style={{ fontFamily: "var(--font-sans)" }}>
              Simulation Configuration
            </h1>
            <p className="text-xs mt-1" style={{ color: "var(--muted-foreground)" }}>
              {route.name} · {route.distance.toFixed(1)} km
            </p>
          </div>

          <SectionHead title="Rider" />
          <Field label="Total Mass" name="mass" value={form.mass} onChange={handleChange} unit="kg" hint="Rider + bike + kit" min={40} max={150} />
          {errors.mass && <p className="text-xs" style={{ color: "#ef4444" }}>{errors.mass}</p>}
          <Field label="FTP" name="ftp" value={form.ftp} onChange={handleChange} unit="W" hint="Functional Threshold Power" min={50} max={600} />
          {errors.ftp && <p className="text-xs" style={{ color: "#ef4444" }}>{errors.ftp}</p>}
          <Field label="CdA" name="cda" value={form.cda} onChange={handleChange} unit="m²" hint="Drag area (position + equipment)" min={0.1} max={0.8} step={0.01} />
          {errors.cda && <p className="text-xs" style={{ color: "#ef4444" }}>{errors.cda}</p>}
          <Field label="Crr" name="crr" value={form.crr} onChange={handleChange} hint="Rolling resistance coefficient" min={0.001} max={0.02} step={0.001} />
          {errors.crr && <p className="text-xs" style={{ color: "#ef4444" }}>{errors.crr}</p>}

          <SectionHead title="Environment" />
          <Field label="Wind Speed" name="windSpeed" value={form.windSpeed} onChange={handleChange} unit="m/s" min={0} max={30} step={0.5} />
          <div className="space-y-1">
            <label className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Wind Bearing
            </label>
            <input
              type="range"
              name="windBearing"
              value={form.windBearing}
              onChange={handleChange}
              min={0}
              max={359}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs mono" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              <span>0° Headwind</span>
              <span>{form.windBearing}°</span>
              <span>180° Tailwind</span>
            </div>
          </div>
          <Field label="Temperature" name="temperature" value={form.temperature} onChange={handleChange} unit="°C" min={-20} max={45} />

          <SectionHead title="Strategy — Constant Power" />
          <div className="space-y-1">
            <Field
              label="Target Power"
              name="targetPower"
              value={form.targetPower}
              onChange={handleChange}
              unit="W"
              hint="Physics-realized power may differ on steep descents (force-limited)"
              min={50}
              max={700}
            />
            {errors.targetPower && <p className="text-xs" style={{ color: "#ef4444" }}>{errors.targetPower}</p>}
            <div className="flex items-center justify-between mt-1">
              <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                % of FTP
              </span>
              <span
                className="text-sm mono font-semibold"
                style={{
                  color: parseFloat(pctFtp) > 100 ? "#ef4444" : parseFloat(pctFtp) > 90 ? "#f59e0b" : "var(--primary)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {pctFtp}%
              </span>
            </div>
          </div>

          <div
            className="border rounded px-3 py-2.5 text-xs space-y-1"
            style={{ border: "1px solid var(--border)", background: "var(--muted)", color: "var(--muted-foreground)" }}
          >
            <div className="font-semibold" style={{ color: "var(--foreground)" }}>
              Future strategies — not available in MVP:
            </div>
            <div>Variable power / W-prime pacing · RL optimizer · Power-duration model</div>
          </div>

          <SectionHead title="Simulation Engine" />
          <Field label="Time Step" name="timeStepS" value={form.timeStepS} onChange={handleChange} unit="s" hint="Simulated seconds per tick" min={1} max={60} />
          <Field label="Tick Interval" name="tickIntervalMs" value={form.tickIntervalMs} onChange={handleChange} unit="ms" hint="Real-time interval between ticks" min={50} max={2000} />

          {startError && (
            <div className="border rounded px-3 py-2 text-xs" style={{ border: "1px solid #ef4444", background: "rgba(239,68,68,0.08)", color: "#ef4444" }}>
              {startError}
            </div>
          )}

          <button
            type="submit"
            disabled={starting}
            className="w-full py-2.5 text-sm font-semibold rounded hover:opacity-90 transition-opacity disabled:opacity-50"
            style={{ background: "var(--primary)", color: "var(--primary-foreground)", fontFamily: "var(--font-sans)" }}
          >
            {starting ? "Starting…" : "▶ Start Simulation"}
          </button>
        </form>

        {/* Route preview */}
        <div className="flex-1 space-y-4">
          <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
            <div className="px-3 py-2 border-b flex justify-between items-center" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                Elevation Profile
              </span>
              <span className="text-xs mono" style={{ color: "var(--muted-foreground)" }}>
                {route.elevationGain} m gain · {route.maxElevation} m max
              </span>
            </div>
            <div className="p-3">
              <ElevationProfile route={route} heightPx={160} />
            </div>
          </div>

          {/* Config summary */}
          <div className="grid grid-cols-3 gap-px" style={{ background: "var(--border)" }}>
            {[
              { label: "W/kg", value: (parseFloat(form.targetPower) / parseFloat(form.mass)).toFixed(2) },
              { label: "CdA×Crr", value: (parseFloat(form.cda) * parseFloat(form.crr)).toFixed(5) },
              { label: "Air density", value: (1.225 * Math.exp(-0.0001 * route.minElevation)).toFixed(3) + " kg/m³" },
            ].map((s) => (
              <div key={s.label} className="px-4 py-3" style={{ background: "var(--card)" }}>
                <div className="text-xs uppercase tracking-widest mb-0.5" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                  {s.label}
                </div>
                <div className="text-lg font-semibold mono" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
                  {isFinite(parseFloat(s.value.split(" ")[0])) ? s.value : "--"}
                </div>
              </div>
            ))}
          </div>

          <div
            className="border rounded px-4 py-3 text-xs space-y-1"
            style={{ border: "1px solid var(--border)", background: "var(--card)", color: "var(--muted-foreground)" }}
          >
            <p>
              <strong style={{ color: "var(--foreground)" }}>Note:</strong> This configuration is sent to the FastAPI backend. All physics, simulation state, and force calculations live on the backend; the UI streams telemetry over WebSocket and is a display layer only.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
