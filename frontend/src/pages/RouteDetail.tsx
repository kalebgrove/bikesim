import { useState } from "react";
import { useParams, Link } from "react-router";
import { useRoute, useSimulations } from "../hooks/useStore";
import ElevationProfile from "../components/ElevationProfile";
import RouteSvg from "../components/RouteSvg";
import { ButtonLink, EmptyState, PageHeader, Panel, StatCell, StatStrip, StatusBadge } from "../components/ui";
import { GRADE_BANDS, gradeBand } from "../lib/grade";
import { fmtDate, fmtDuration, fixed } from "../lib/format";

export default function RouteDetail() {
  const { routeId } = useParams<{ routeId: string }>();
  const route = useRoute(routeId);
  const allSims = useSimulations();
  const [hoverDistKm, setHoverDistKm] = useState<number | null>(null);

  if (!route) {
    return (
      <EmptyState title="Route not found">
        <Link to="/upload" className="text-accent hover:underline">
          Import a GPX route
        </Link>
      </EmptyState>
    );
  }

  const routeSims = allSims.filter((s) => s.routeId === route.id);
  const nPts = route.points.length || 1;
  const bandShare = GRADE_BANDS.map((b) => ({
    ...b,
    pct: (route.points.filter((p) => gradeBand(p.grade) === b).length / nPts) * 100,
  }));
  const maxGrade = route.points.reduce((m, p) => Math.max(m, p.grade), -Infinity);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
      <PageHeader
        eyebrow={`Route · imported ${fmtDate(route.uploadedAt)}`}
        title={route.name}
        subtitle={`${route.points.length.toLocaleString()} track points`}
        actions={
          <ButtonLink to={`/routes/${route.id}/configure`} variant="primary">
            Configure run
          </ButtonLink>
        }
      />

      <StatStrip cols="grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
        <StatCell label="Distance" value={fixed(route.distance, 2)} unit="km" />
        <StatCell label="Elevation gain" value={route.elevationGain.toLocaleString()} unit="m" />
        <StatCell label="Elevation loss" value={route.elevationLoss.toLocaleString()} unit="m" />
        <StatCell label="Max elevation" value={route.maxElevation.toLocaleString()} unit="m" />
        <StatCell label="Min elevation" value={route.minElevation.toLocaleString()} unit="m" />
        <StatCell label="Max grade" value={fixed(maxGrade)} unit="%" tone={maxGrade > 10 ? "warn" : "default"} />
      </StatStrip>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6">
        <div className="space-y-6 min-w-0">
          <Panel title="Route map" meta="Coloured by grade · hover to inspect" bodyClassName="h-[380px]">
            <RouteSvg route={route} width={800} height={380} hoverDistKm={hoverDistKm} onHoverDistKm={setHoverDistKm} />
          </Panel>
          <Panel title="Elevation profile" bodyClassName="px-2 py-3">
            <ElevationProfile route={route} heightPx={170} hoverDistKm={hoverDistKm} />
          </Panel>
        </div>

        <Panel title="Grade distribution" meta="Share of track points" bodyClassName="p-4 space-y-3.5">
          {bandShare.map((b) => (
            <div key={b.label} className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="flex items-center gap-2 text-dim">
                  <span className="size-2 rounded-sm" style={{ background: b.color }} />
                  {b.label}
                </span>
                <span className="num text-fg">{b.pct.toFixed(0)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-panel-2 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${b.pct}%`, background: b.color }} />
              </div>
            </div>
          ))}
        </Panel>
      </div>

      <Panel title="Runs on this route" meta={`${routeSims.length}`} bodyClassName="">
        {routeSims.length === 0 ? (
          <EmptyState title="No runs yet">Configure a run to simulate this route.</EmptyState>
        ) : (
          <div className="divide-y divide-line">
            {routeSims.map((sim) => (
              <div key={sim.id} className="flex items-center gap-6 px-4 h-12">
                <StatusBadge status={sim.status} />
                <span className="num text-xs text-faint w-28 truncate">{sim.id}</span>
                <span className="num text-[13px]">{sim.config.strategy.targetPower} W</span>
                <span className="num text-[13px] text-dim">{sim.config.rider.mass} kg</span>
                <span className="num text-[13px] text-dim">{sim.summary ? fmtDuration(sim.summary.totalTimeS) : "--"}</span>
                <span className="num text-[13px] text-dim">{sim.summary ? `${fixed(sim.summary.avgSpeedKph)} km/h` : ""}</span>
                <div className="ml-auto">
                  {sim.status === "complete" ? (
                    <ButtonLink to={`/simulations/${sim.id}/results`} size="sm">
                      Results
                    </ButtonLink>
                  ) : (
                    <ButtonLink to={`/simulations/${sim.id}/live`} size="sm">
                      Live view
                    </ButtonLink>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
