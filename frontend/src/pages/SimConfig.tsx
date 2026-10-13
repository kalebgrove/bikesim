import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { useRoute } from "../hooks/useStore";
import { useSimEngineContext } from "../lib/simEngineContext";
import type { SimConfig as SimConfigType } from "../lib/types";
import ElevationProfile from "../components/ElevationProfile";
import { Button, Callout, EmptyState, PageHeader, Panel, Stat } from "../components/ui";
import { fixed } from "../lib/format";

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

type Errors = Partial<Record<keyof FormState, string>>;

// [min, max, message] — timeStepS max matches the backend schema (le=10)
const LIMITS: Record<keyof FormState, [number, number, string]> = {
  mass: [40, 150, "40 – 150 kg"],
  ftp: [50, 600, "50 – 600 W"],
  cda: [0.1, 0.8, "0.10 – 0.80 m²"],
  crr: [0.001, 0.02, "0.001 – 0.020"],
  windSpeed: [0, 30, "0 – 30 m/s"],
  windBearing: [0, 360, "0 – 360°"],
  temperature: [-20, 45, "-20 – 45 °C"],
  targetPower: [50, 700, "50 – 700 W"],
  timeStepS: [0.1, 10, "0.1 – 10 s"],
  tickIntervalMs: [50, 2000, "50 – 2000 ms"],
};

const SEA_LEVEL_RHO = 1.225; // kg/m³, ISA sea level

function Field({
  label,
  name,
  value,
  onChange,
  unit,
  hint,
  error,
  step = 1,
}: {
  label: string;
  name: keyof FormState;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  unit?: string;
  hint?: string;
  error?: string;
  step?: number;
}) {
  const [min, max] = LIMITS[name];
  return (
    <div className="space-y-1.5">
      <label htmlFor={name} className="label block">
        {label}
      </label>
      <div
        className={`flex items-center h-9 rounded-md bg-panel-2 border transition-colors focus-within:border-accent ${
          error ? "border-err/70" : "border-line hover:border-line-strong"
        }`}
      >
        <input
          id={name}
          type="number"
          name={name}
          value={value}
          onChange={onChange}
          min={min}
          max={max}
          step={step}
          className="num flex-1 min-w-0 h-full px-3 bg-transparent text-fg outline-none"
        />
        {unit && <span className="num text-xs text-faint pr-3">{unit}</span>}
      </div>
      <p className={`text-xs ${error ? "text-err" : "text-faint"}`}>{error ? `Allowed range: ${error}` : hint}</p>
    </div>
  );
}

/** Compass showing where the wind blows FROM (meteorological convention, clockwise from north). */
function WindCompass({ bearing, speed }: { bearing: number; speed: number }) {
  const rad = (bearing * Math.PI) / 180;
  const r = 44;
  // Arrow runs from the "from" side towards the centre, in screen coords (y down)
  const x0 = 60 + Math.sin(rad) * r;
  const y0 = 60 - Math.cos(rad) * r;
  const x1 = 60 + Math.sin(rad) * 8;
  const y1 = 60 - Math.cos(rad) * 8;
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" className="shrink-0">
      <defs>
        <marker id="windHead" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0 0L10 5L0 10z" fill="#5b9dff" />
        </marker>
      </defs>
      <circle cx="60" cy="60" r="52" fill="#181c25" stroke="#333a48" />
      {Array.from({ length: 36 }, (_, i) => {
        const a = (i * 10 * Math.PI) / 180;
        const long = i % 9 === 0;
        return (
          <line
            key={i}
            x1={60 + Math.sin(a) * 52}
            y1={60 - Math.cos(a) * 52}
            x2={60 + Math.sin(a) * (long ? 45 : 49)}
            y2={60 - Math.cos(a) * (long ? 45 : 49)}
            stroke={long ? "#9aa3b2" : "#333a48"}
          />
        );
      })}
      <g fontSize="9" fontFamily="JetBrains Mono" fill="#636c7c" textAnchor="middle">
        <text x="60" y="36">N</text>
        <text x="86" y="63">E</text>
        <text x="60" y="90">S</text>
        <text x="34" y="63">W</text>
      </g>
      {speed > 0 && <line x1={x0} y1={y0} x2={x1} y2={y1} stroke="#5b9dff" strokeWidth="2.5" markerEnd="url(#windHead)" />}
      <circle cx="60" cy="60" r="2.5" fill="#e7eaf0" />
    </svg>
  );
}

const COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

/** Coggan power-zone name for a fraction of FTP. */
function intensityZone(pct: number): string {
  if (pct < 55) return "Z1 · Recovery";
  if (pct < 76) return "Z2 · Endurance";
  if (pct < 91) return "Z3 · Tempo";
  if (pct < 106) return "Z4 · Threshold";
  if (pct < 121) return "Z5 · VO₂max";
  return "Z6 · Anaerobic";
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
  const [errors, setErrors] = useState<Errors>({});
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const n = (k: keyof FormState) => parseFloat(form[k]);

  function validate(): boolean {
    const errs: Errors = {};
    for (const k of Object.keys(LIMITS) as (keyof FormState)[]) {
      const [min, max, msg] = LIMITS[k];
      const v = n(k);
      if (!isFinite(v) || v < min || v > max) errs[k] = msg;
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate() || !routeId || !route || starting) return;

    const config: SimConfigType = {
      routeId,
      rider: { mass: n("mass"), ftp: n("ftp"), cda: n("cda"), crr: n("crr") },
      environment: {
        windSpeed: n("windSpeed"),
        windBearing: n("windBearing"),
        temperature: n("temperature"),
        airDensity: SEA_LEVEL_RHO, // sea level; the backend corrects it for elevation along the route
      },
      strategy: { type: "constant_power", targetPower: n("targetPower") },
      simSettings: { timeStepS: n("timeStepS"), tickIntervalMs: n("tickIntervalMs") },
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
      <EmptyState title="Route not found">
        <Link to="/upload" className="text-accent hover:underline">
          Import a GPX route
        </Link>
      </EmptyState>
    );
  }

  const pctFtp = (n("targetPower") / n("ftp")) * 100;
  const wPerKg = n("targetPower") / n("mass");
  const realtime = (n("timeStepS") / n("tickIntervalMs")) * 1000;
  const bearing = isFinite(n("windBearing")) ? n("windBearing") : 0;
  const hasErrors = Object.values(errors).some(Boolean);

  return (
    <form onSubmit={handleSubmit} className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
      <PageHeader
        eyebrow="Configure run"
        title={route.name}
        subtitle={`${route.distance.toFixed(1)} km · ${route.elevationGain} m gain · ${route.points.length.toLocaleString()} points`}
        actions={
          <>
            <Link to={`/routes/${route.id}`} className="text-[13px] text-dim hover:text-fg px-2">
              Cancel
            </Link>
            <Button type="submit" variant="primary" disabled={starting}>
              {starting ? "Starting…" : "Start simulation"}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          <Panel title="Rider" meta="Mass, power and resistance coefficients">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
              <Field label="System mass" name="mass" value={form.mass} onChange={handleChange} unit="kg" hint="Rider + bike + kit" error={errors.mass} />
              <Field label="FTP" name="ftp" value={form.ftp} onChange={handleChange} unit="W" hint="Functional threshold power (= CP for W′)" error={errors.ftp} />
              <Field label="Drag area CdA" name="cda" value={form.cda} onChange={handleChange} unit="m²" hint="Position + equipment; hoods ≈ 0.32, TT ≈ 0.22" error={errors.cda} step={0.01} />
              <Field label="Rolling resistance Crr" name="crr" value={form.crr} onChange={handleChange} unit="–" hint="Good road tyres ≈ 0.004" error={errors.crr} step={0.001} />
            </div>
          </Panel>

          <Panel title="Environment" meta="Wind and air">
            <div className="flex flex-col md:flex-row gap-6">
              <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
                <Field label="Wind speed" name="windSpeed" value={form.windSpeed} onChange={handleChange} unit="m/s" hint={`${fixed(n("windSpeed") * 3.6)} km/h`} error={errors.windSpeed} step={0.5} />
                <Field label="Temperature" name="temperature" value={form.temperature} onChange={handleChange} unit="°C" hint="Recorded with the run; not used by the physics yet" error={errors.temperature} />
                <div className="sm:col-span-2 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="windBearing" className="label">
                      Wind direction (from)
                    </label>
                    <span className="num text-xs text-dim">
                      {COMPASS_POINTS[Math.round(bearing / 45) % 8]} · {bearing.toFixed(0)}°
                    </span>
                  </div>
                  <input id="windBearing" type="range" name="windBearing" value={form.windBearing} onChange={handleChange} min={0} max={359} step={1} className="w-full" />
                  <div className="num flex justify-between text-[11px] text-faint">
                    <span>0° N</span>
                    <span>90° E</span>
                    <span>180° S</span>
                    <span>270° W</span>
                  </div>
                  <p className="text-xs text-faint">
                    Meteorological convention: the compass direction the wind blows <em>from</em>. Head/tailwind depends on the route heading at each point.
                  </p>
                </div>
              </div>
              <div className="flex flex-col items-center gap-2 md:pt-5">
                <WindCompass bearing={bearing} speed={n("windSpeed")} />
                <span className="text-[11px] text-faint">Arrow = air flow</span>
              </div>
            </div>
          </Panel>

          <Panel title="Pacing strategy" meta="Constant power">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
              <Field
                label="Target power"
                name="targetPower"
                value={form.targetPower}
                onChange={handleChange}
                unit="W"
                hint="Pedal power; realized power can fall below target when coasting"
                error={errors.targetPower}
              />
              <div className="space-y-1.5">
                <span className="label block">Intensity</span>
                <div className="h-9 flex items-center gap-3">
                  <div className="flex-1 h-1.5 rounded-full bg-panel-2 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${pctFtp > 100 ? "bg-err" : pctFtp > 90 ? "bg-warn" : "bg-accent"}`}
                      style={{ width: `${Math.min(100, (pctFtp / 130) * 100) || 0}%` }}
                    />
                  </div>
                  <span className={`num text-[13px] font-semibold ${pctFtp > 100 ? "text-err" : pctFtp > 90 ? "text-warn" : "text-accent"}`}>
                    {fixed(pctFtp, 0)}% FTP
                  </span>
                </div>
                <p className="text-xs text-faint">{isFinite(pctFtp) ? intensityZone(pctFtp) : "--"}</p>
              </div>
            </div>
          </Panel>

          <Panel title="Engine" meta="Integration and playback">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
              <Field label="Time step" name="timeStepS" value={form.timeStepS} onChange={handleChange} unit="s" hint="Simulated seconds per tick (sub-stepped internally)" error={errors.timeStepS} step={0.1} />
              <Field label="Tick interval" name="tickIntervalMs" value={form.tickIntervalMs} onChange={handleChange} unit="ms" hint="Wall-clock delay between streamed ticks" error={errors.tickIntervalMs} step={10} />
            </div>
          </Panel>
        </div>

        <div className="space-y-6 xl:sticky xl:top-6">
          <Panel title="Run summary">
            <div className="grid grid-cols-2 gap-x-4 gap-y-5">
              <Stat label="Target" value={fixed(n("targetPower"), 0)} unit="W" tone="accent" />
              <Stat label="Power / mass" value={fixed(wPerKg, 2)} unit="W/kg" />
              <Stat label="Wind" value={fixed(n("windSpeed"), 1)} unit="m/s" sub={`from ${bearing.toFixed(0)}°`} />
              <Stat label="Air density ρ₀" value={SEA_LEVEL_RHO.toFixed(3)} unit="kg/m³" sub="Sea level; corrected per point" />
              <Stat label="Playback" value={fixed(realtime, 0)} unit="× real time" />
              <Stat label="Distance" value={fixed(route.distance, 1)} unit="km" />
            </div>
          </Panel>

          <Panel title="Elevation" bodyClassName="px-2 py-3">
            <ElevationProfile route={route} heightPx={140} gradientId="cfgElev" />
          </Panel>

          {hasErrors && <Callout tone="err" title="Check highlighted fields">Some values are outside the allowed range.</Callout>}
          {startError && <Callout tone="err" title="Could not start simulation">{startError}</Callout>}

          <Button type="submit" variant="primary" disabled={starting} className="w-full">
            {starting ? "Starting…" : "Start simulation"}
          </Button>
        </div>
      </div>
    </form>
  );
}
