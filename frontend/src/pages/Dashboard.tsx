import { Link } from "react-router";
import { useRoutes, useSimulations } from "../hooks/useStore";
import { fmtDate, fmtDuration, fixed } from "../lib/format";
import { ButtonLink, EmptyState, PageHeader, Panel, StatCell, StatStrip, StatusBadge } from "../components/ui";

const th = "label text-left font-medium px-4 h-9 border-b border-line";
const td = "px-4 h-11 border-b border-line";

export default function Dashboard() {
  const routes = useRoutes();
  const sims = useSimulations();
  const completed = sims.filter((s) => s.status === "complete");
  const active = sims.filter((s) => s.status === "running" || s.status === "paused");

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
      <PageHeader
        eyebrow="Workspace"
        title="Overview"
        subtitle="Import a GPX route, configure the rider and environment, and run a physics simulation."
        actions={
          <ButtonLink to="/upload" variant="primary">
            Import GPX
          </ButtonLink>
        }
      />

      <StatStrip cols="grid-cols-2 lg:grid-cols-4">
        <StatCell label="Routes" value={routes.length} />
        <StatCell label="Runs" value={sims.length} />
        <StatCell label="Active" value={active.length} tone={active.length ? "ok" : "default"} />
        <StatCell label="Completed" value={completed.length} tone="accent" />
      </StatStrip>

      <Panel title="Routes" meta={`${routes.length} loaded`} bodyClassName="overflow-x-auto" actions={<ButtonLink to="/upload" size="sm" variant="ghost">+ Import</ButtonLink>}>
        {routes.length === 0 ? (
          <EmptyState title="No routes yet">Import a GPX track with elevation data to get started.</EmptyState>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr>
                <th className={th}>Name</th>
                <th className={`${th} text-right`}>Distance</th>
                <th className={`${th} text-right`}>Gain</th>
                <th className={`${th} text-right`}>Loss</th>
                <th className={`${th} text-right`}>Max elev.</th>
                <th className={th}>Imported</th>
                <th className={th} />
              </tr>
            </thead>
            <tbody>
              {routes.map((r) => (
                <tr key={r.id} className="hover:bg-panel-2/50 [&:last-child>td]:border-b-0">
                  <td className={td}>
                    <Link to={`/routes/${r.id}`} className="font-medium text-fg hover:text-accent">
                      {r.name}
                    </Link>
                  </td>
                  <td className={`${td} num text-right`}>{r.distance.toFixed(1)} km</td>
                  <td className={`${td} num text-right`}>{r.elevationGain} m</td>
                  <td className={`${td} num text-right`}>{r.elevationLoss} m</td>
                  <td className={`${td} num text-right`}>{r.maxElevation} m</td>
                  <td className={`${td} text-dim`}>{fmtDate(r.uploadedAt)}</td>
                  <td className={`${td} text-right`}>
                    <ButtonLink to={`/routes/${r.id}/configure`} size="sm">
                      Configure run
                    </ButtonLink>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Runs" meta="This session" bodyClassName="overflow-x-auto">
        {sims.length === 0 ? (
          <EmptyState title="No runs yet">Pick a route, set the rider and pacing, and start your first simulation.</EmptyState>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr>
                <th className={th}>Route</th>
                <th className={th}>Status</th>
                <th className={`${th} text-right`}>Target power</th>
                <th className={`${th} text-right`}>Mass</th>
                <th className={`${th} text-right`}>Time</th>
                <th className={`${th} text-right`}>Avg speed</th>
                <th className={th}>Started</th>
                <th className={th} />
              </tr>
            </thead>
            <tbody>
              {sims.map((s) => (
                <tr key={s.id} className="hover:bg-panel-2/50 [&:last-child>td]:border-b-0">
                  <td className={`${td} font-medium`}>{s.routeName}</td>
                  <td className={td}>
                    <StatusBadge status={s.status} />
                  </td>
                  <td className={`${td} num text-right`}>{s.config.strategy.targetPower} W</td>
                  <td className={`${td} num text-right`}>{s.config.rider.mass} kg</td>
                  <td className={`${td} num text-right`}>{s.summary ? fmtDuration(s.summary.totalTimeS) : "--"}</td>
                  <td className={`${td} num text-right`}>{s.summary ? `${fixed(s.summary.avgSpeedKph)} km/h` : "--"}</td>
                  <td className={`${td} text-dim`}>{fmtDate(s.startedAt ?? s.createdAt)}</td>
                  <td className={`${td} text-right`}>
                    {s.status === "complete" ? (
                      <ButtonLink to={`/simulations/${s.id}/results`} size="sm">
                        Results
                      </ButtonLink>
                    ) : (
                      <ButtonLink to={`/simulations/${s.id}/live`} size="sm" variant={s.status === "stopped" ? "secondary" : "primary"}>
                        Live view
                      </ButtonLink>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
