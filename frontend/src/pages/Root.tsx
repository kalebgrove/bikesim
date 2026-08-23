import { Outlet } from "react-router";
import Navbar from "../components/Navbar";

export default function Root() {
  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: "var(--background)" }}>
      <Navbar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
