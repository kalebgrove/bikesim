import { Fragment } from "react";
import { Link, useLocation } from "react-router";
import { useRoute, useSimulation } from "../hooks/useStore";

interface Crumb {
  label: string;
  to?: string;
}

function useCrumbs(): Crumb[] {
  const [first, id, leaf] = useLocation().pathname.split("/").filter(Boolean);
  const sim = useSimulation(first === "simulations" ? id : undefined);
  const route = useRoute(first === "routes" ? id : sim?.routeId);

  const crumbs: Crumb[] = [{ label: "Overview", to: "/" }];
  if (first === "upload") crumbs.push({ label: "Import GPX" });
  if (route) crumbs.push({ label: route.name, to: `/routes/${route.id}` });
  if (first === "routes" && leaf === "configure") crumbs.push({ label: "Configure run" });
  if (sim) crumbs.push({ label: leaf === "results" ? "Results" : "Live run" });
  return crumbs;
}

export default function Topbar() {
  const crumbs = useCrumbs();
  return (
    <header className="h-14 shrink-0 border-b border-line bg-bg/80 backdrop-blur flex items-center px-6">
      <nav className="flex items-center gap-2 text-[13px] min-w-0">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <Fragment key={i}>
              {i > 0 && <span className="text-faint">/</span>}
              {c.to && !last ? (
                <Link to={c.to} className="text-dim hover:text-fg truncate">
                  {c.label}
                </Link>
              ) : (
                <span className={`truncate ${last ? "text-fg font-medium" : "text-dim"}`}>{c.label}</span>
              )}
            </Fragment>
          );
        })}
      </nav>
    </header>
  );
}
