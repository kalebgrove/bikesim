import { createBrowserRouter } from "react-router";
import Root from "../pages/Root";
import Dashboard from "../pages/Dashboard";
import GPXUpload from "../pages/GPXUpload";
import RouteDetail from "../pages/RouteDetail";
import SimConfig from "../pages/SimConfig";
import LiveSim from "../pages/LiveSim";
import Results from "../pages/Results";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: Dashboard },
      { path: "upload", Component: GPXUpload },
      { path: "routes/:routeId", Component: RouteDetail },
      { path: "routes/:routeId/configure", Component: SimConfig },
      { path: "simulations/:simId/live", Component: LiveSim },
      { path: "simulations/:simId/results", Component: Results },
    ],
  },
]);
