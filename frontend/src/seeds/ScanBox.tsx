import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { uploadMedia } from "../media/hooks";
import { useScanActions, useScans, type Scan } from "./hooks";

type Row = { key: string; name: string; state: "uploading" | "starting" | "error"; progress?: number; error?: string };

const LABEL: Record<string, string> = { queued: "Waiting its turn…", running: "Reading…" };

/** Pick photos of the backs of packets; each is uploaded and read into a draft to review. */
export default function ScanBox({ allotmentId }: { allotmentId: number }) {
  const input = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const scans = useScans(allotmentId);
  const actions = useScanActions(allotmentId);

  const patchRow = (key: string, change: Partial<Row>) => setRows((all) => all.map((r) => (r.key === key ? { ...r, ...change } : r)));

  async function pick(files: FileList | null) {
    if (!files?.length) return;
    const picked = Array.from(files);
    const added = picked.map((f, i) => ({ key: `${Date.now()}-${i}`, name: f.name, state: "uploading" as const, progress: 0 }));
    setRows((all) => [...added, ...all]);
    for (const [i, file] of picked.entries()) {
      const key = added[i].key;
      try {
        const media = await uploadMedia(allotmentId, { file }, (p) => patchRow(key, { progress: p }));
        patchRow(key, { state: "starting" });
        await actions.start.mutateAsync(media.id!);
        setRows((all) => all.filter((r) => r.key !== key)); // from here the scan itself is listed
      } catch (err) {
        patchRow(key, { state: "error", error: (err as Error).message });
      }
    }
    if (input.current) input.current.value = "";
  }

  const recent = (scans.data ?? []).filter((s) => s.status !== "ready" || isFresh(s)).slice(0, 8);
  return (
    <section className="scan-box" aria-label="Scan packets">
      <div className="inline">
        <label className="file">
          <span className="button">Scan packets</span>
          <input ref={input} type="file" accept="image/*" multiple capture="environment" className="sr-only" aria-label="Photos of packet backs" onChange={(e) => void pick(e.target.files)} />
        </label>
        <span className="hint">Photograph the back of each packet, flat and in good light. Several at once is fine.</span>
      </div>
      {(rows.length > 0 || recent.length > 0) && (
        <ul className="scan-list">
          {rows.map((r) => (
            <li key={r.key}>
              <span>{r.name}</span>
              <span className={r.state === "error" ? "error" : "muted"}>
                {r.state === "uploading" ? `Uploading ${Math.round((r.progress ?? 0) * 100)}%` : r.state === "starting" ? "Starting…" : r.error}
              </span>
            </li>
          ))}
          {recent.map((s) => (
            <li key={s.id}>
              <span>Packet photo {s.id}</span>
              {s.status === "ready" && s.packet_id ? (
                <Link to={String(s.packet_id)}>Review the draft</Link>
              ) : s.status === "failed" ? (
                <span>
                  <span className="error">{s.error ?? "Couldn't read it"}</span>{" "}
                  <button type="button" className="link" onClick={() => actions.retry.mutate(s.id!)}>Try again</button>
                </span>
              ) : (
                <span className="muted">{LABEL[s.status ?? ""] ?? s.status}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** A finished scan stays listed for a day, so the draft is easy to find again. */
function isFresh(s: Scan): boolean {
  return !!s.finished_at && Date.now() - new Date(s.finished_at).getTime() < 24 * 3600 * 1000;
}
