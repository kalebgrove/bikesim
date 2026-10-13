import { Outlet } from "react-router";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";

export default function Root() {
  return (
    <div className="flex h-full overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar />
        <main className="flex-1 overflow-auto min-h-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
