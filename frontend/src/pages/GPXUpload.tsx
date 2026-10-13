import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router";
import { fetchRouteGeometry, uploadRoute } from "../lib/api";
import { upsertRoute } from "../lib/store";
import { Button, Callout, PageHeader, Panel } from "../components/ui";

type UploadState = "idle" | "uploading" | "error";

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
    <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
      <PageHeader
        eyebrow="Routes"
        title="Import GPX route"
        subtitle="The track is parsed, smoothed and resampled by the backend. Elevation data is required."
      />

      <Panel title="Source file">
        <div className="space-y-5">
          <div className="space-y-1.5">
            <label htmlFor="routeName" className="label">
              Route name <span className="normal-case tracking-normal text-faint">(optional)</span>
            </label>
            <input
              id="routeName"
              type="text"
              value={routeName}
              onChange={(e) => setRouteName(e.target.value)}
              placeholder="Defaults to the file name"
              className="w-full h-9 px-3 rounded-md bg-panel-2 border border-line text-fg placeholder:text-faint outline-none focus:border-accent"
            />
          </div>

          <div
            onDrop={onDrop}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => state !== "uploading" && inputRef.current?.click()}
            className={`rounded-lg border border-dashed cursor-pointer transition-colors flex flex-col items-center justify-center gap-3 py-14 ${
              dragOver ? "border-accent bg-accent/5" : "border-line-strong bg-panel-2/40 hover:bg-panel-2"
            }`}
          >
            <input ref={inputRef} type="file" accept=".gpx,application/gpx+xml,text/xml" onChange={onFileChange} className="hidden" />
            {state === "uploading" ? (
              <>
                <div className="size-7 rounded-full border-2 border-accent border-t-transparent animate-spin" />
                <span className="text-dim">
                  Processing <span className="num text-fg">{fileName}</span>…
                </span>
              </>
            ) : (
              <>
                <div className={`size-10 rounded-lg grid place-items-center ${dragOver ? "bg-accent/15 text-accent" : "bg-panel-2 text-dim"}`}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v4h16v-4" />
                  </svg>
                </div>
                <div className="text-center">
                  <p className="font-medium text-fg">Drop a .gpx file here, or click to browse</p>
                  <p className="text-xs text-faint mt-1">
                    Track points (<code className="num">trkpt</code>) must include <code className="num">ele</code>
                  </p>
                </div>
              </>
            )}
          </div>

          {state === "error" && (
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <Callout tone="err" title="Import failed">
                  {errorMsg}
                </Callout>
              </div>
              <Button size="sm" onClick={() => setState("idle")}>
                Dismiss
              </Button>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
