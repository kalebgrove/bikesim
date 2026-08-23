import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router";
import { fetchRouteGeometry, uploadRoute } from "../lib/api";
import { upsertRoute } from "../lib/store";

type UploadState = "idle" | "uploading" | "success" | "error";

export default function GPXUpload() {
  const navigate = useNavigate();
  const [dragOver, setDragOver] = useState(false);
  const [state, setState] = useState<UploadState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [routeName, setRouteName] = useState("");
  const [fileName, setFileName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback(
    async (file: File, name: string) => {
      if (!file.name.toLowerCase().endsWith(".gpx") && !file.type.includes("xml")) {
        setErrorMsg("File must be a .gpx file.");
        setState("error");
        return;
      }
      setState("uploading");
      setFileName(file.name);
      try {
        const row = await uploadRoute(file, name || file.name.replace(/\.gpx$/i, ""));
        const route = await fetchRouteGeometry(String(row.id));
        upsertRoute(route);
        navigate(`/routes/${route.id}`);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Upload failed");
        setState("error");
      }
    },
    [navigate]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) void processFile(file, routeName);
    },
    [processFile, routeName]
  );

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void processFile(file, routeName);
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold mb-1" style={{ fontFamily: "var(--font-sans)" }}>
          Upload GPX Route
        </h1>
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Upload a GPX track file. Elevation data (<code className="mono">ele</code> elements) is required for simulation.
        </p>
      </div>

      {/* Route name */}
      <div className="space-y-1.5">
        <label className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
          Route Name (optional)
        </label>
        <input
          type="text"
          value={routeName}
          onChange={(e) => setRouteName(e.target.value)}
          placeholder="e.g. Strade Bianche 2025"
          className="w-full px-3 py-2 text-sm rounded border outline-none focus:ring-1"
          style={{
            background: "var(--secondary)",
            border: "1px solid var(--border)",
            color: "var(--foreground)",
            fontFamily: "var(--font-body)",
          }}
        />
      </div>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed rounded cursor-pointer transition-all flex flex-col items-center justify-center gap-3 py-14"
        style={{
          borderColor: dragOver ? "var(--primary)" : "var(--border)",
          background: dragOver ? "rgba(56,189,248,0.04)" : "var(--card)",
        }}
      >
        <input ref={inputRef} type="file" accept=".gpx,application/gpx+xml,text/xml" onChange={onFileChange} className="hidden" />
        {state === "uploading" ? (
          <>
            <div className="size-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }} />
            <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
              Uploading {fileName}…
            </span>
          </>
        ) : (
          <>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={dragOver ? "var(--primary)" : "var(--muted-foreground)"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                Drop .gpx file here or click to browse
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted-foreground)" }}>
                Track must include <code className="mono">trkpt</code> elements with elevation
              </p>
            </div>
          </>
        )}
      </div>

      {state === "error" && (
        <div className="border rounded px-4 py-3 text-sm" style={{ border: "1px solid #ef4444", background: "rgba(239,68,68,0.08)", color: "#ef4444" }}>
          <strong>Upload failed:</strong> {errorMsg}
          <button onClick={() => setState("idle")} className="ml-3 underline text-xs">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
