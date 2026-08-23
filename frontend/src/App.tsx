import { useEffect } from "react";
import { RouterProvider } from "react-router";
import { router } from "./app/routes";
import { useSimEngine } from "./hooks/useSimEngine";
import { SimEngineContext } from "./lib/simEngineContext";
import { loadRoutesFromBackend } from "./lib/backendSync";

export default function App() {
  const engine = useSimEngine();

  useEffect(() => {
    loadRoutesFromBackend();
  }, []);

  return (
    <SimEngineContext.Provider value={engine}>
      <RouterProvider router={router} />
    </SimEngineContext.Provider>
  );
}
