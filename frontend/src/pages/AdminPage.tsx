import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { ago, duration, jobTime } from "../admin/format";
import {
  useAdminJobs,
  useAdminLogs,
  useAdminSystem,
  useAdminWorkers,
  type Job,
  type LogEntry,
  type LogFilter,
  type Worker,
} from "../admin/hooks";

const TABS = [
  ["workers", "Workers"],
  ["jobs", "Jobs"],
  ["logs", "Logs"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function AdminPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  if (!user?.is_admin) {
    return (
      <main className="page">
        <h1>Admin</h1>
        <p>This page is for site admins. An admin can be set with <code>flask make-admin you@example.com</code> on the server.</p>
        <p><Link to="/">Back to your allotments</Link></p>
      </main>
    );
  }
  const requested = params.get("tab");
  const tab: Tab = TABS.some(([key]) => key === requested) ? (requested as Tab) : "workers";
  return (
    <main className="page admin">
      <h1>Admin</h1>
      <div className="pages" role="tablist">
        {TABS.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "page-tab active" : "page-tab"} onClick={() => setParams({ tab: key })}>
            {label}
          </button>
        ))}
      </div>
      {tab === "workers" && <WorkersTab />}
      {tab === "jobs" && <JobsTab />}
      {tab === "logs" && <LogsTab />}
    </main>
  );
}

function Ok({ value }: { value: string }) {
  return <span className={value === "ok" ? "badge ok-badge" : "badge bad-badge"}>{value === "ok" ? "OK" : value}</span>;
}

function WorkersTab() {
  const workers = useAdminWorkers();
  const system = useAdminSystem();
  const w = workers.data;
  const s = system.data;
  return (
    <>
      <section className="admin-section">
        <h2>System</h2>
        {s ? (
          <>
            <ul className="admin-checks">
              {Object.entries(s.checks ?? {}).map(([name, value]) => (
                <li key={name}><span>{name}</span> <Ok value={value} /></li>
              ))}
            </ul>
            <p className="muted">
              Version <strong>{s.version}</strong> · {s.users} {s.users === 1 ? "user" : "users"} · {s.allotments} {s.allotments === 1 ? "allotment" : "allotments"} · {s.log_rows} stored log lines (kept {s.log_retention_days} days)
            </p>
          </>
        ) : (
          <p className="muted">{system.isLoading ? "Checking…" : "Couldn't load the system checks."}</p>
        )}
      </section>

      <section className="admin-section">
        <h2>Workers</h2>
        {workers.isLoading && <p className="muted">Asking the workers…</p>}
        {w?.error && <p className="error">{w.error}</p>}
        {w && !w.error && w.workers?.length === 0 && (
          <p className="error">No worker answered. Jobs will wait in their queues until one starts.</p>
        )}
        <ul className="cards">
          {(w?.workers ?? []).map((worker) => <WorkerCard key={worker.name} worker={worker} />)}
        </ul>
      </section>

      <section className="admin-section">
        <h2>Queues</h2>
        <table className="admin-table">
          <thead><tr><th>Queue</th><th>Waiting</th><th>Workers</th></tr></thead>
          <tbody>
            {(w?.queues ?? []).map((q) => (
              <tr key={q.name}>
                <td>{q.name}</td>
                <td>{q.depth ?? "?"}</td>
                <td className={q.consumers === 0 && (q.depth ?? 0) > 0 ? "bad" : undefined}>
                  {q.consumers}{q.consumers === 0 && (q.depth ?? 0) > 0 ? " – nothing is picking these up" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="admin-section">
        <h2>Schedule</h2>
        <table className="admin-table">
          <thead><tr><th>Job</th><th>When</th><th>Last run</th></tr></thead>
          <tbody>
            {(w?.beat ?? []).map((b) => (
              <tr key={b.name}>
                <td>{b.name}</td>
                <td>{b.schedule}</td>
                <td>
                  {ago(b.last_run)}
                  {b.last_state && b.last_state !== "SUCCESS" && <span className="bad"> ({b.last_state})</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">“Last run” comes from the stored task log, so it fills in as the scheduler runs.</p>
      </section>
    </>
  );
}

function WorkerCard({ worker }: { worker: Worker }) {
  const active = worker.active ?? [];
  return (
    <li className="admin-card">
      <div className="admin-card-head">
        <strong>{worker.name}</strong>
        <span className="badge ok-badge">online</span>
      </div>
      <p className="muted">
        Queues: {(worker.queues ?? []).join(", ") || "–"} · {worker.concurrency ?? "?"} at once · up {duration(worker.uptime_seconds)} · {worker.processed ?? 0} done
        {worker.version ? ` · v${worker.version}` : ""}
        {worker.gpu ? ` · GPU: ${worker.gpu}` : ""}
      </p>
      {active.length === 0 ? (
        <p className="muted">Idle{worker.reserved ? `, ${worker.reserved} waiting` : ""}</p>
      ) : (
        <ul className="admin-active">
          {active.map((t) => (
            <li key={t.id}>{t.name} <span className="muted">for {duration(t.running_seconds)}</span></li>
          ))}
          {worker.reserved ? <li className="muted">{worker.reserved} more waiting</li> : null}
        </ul>
      )}
    </li>
  );
}

const KIND_LABEL: Record<string, string> = { map: "Map jobs", scan: "Packet photos", mastodon: "Mastodon posts" };

function JobsTab() {
  const jobs = useAdminJobs();
  const data = jobs.data;
  if (jobs.isLoading) return <p className="muted">Loading…</p>;
  if (!data) return <p>Couldn't load the jobs.</p>;
  return (
    <>
      <div className="stats">
        {(data.counts ?? []).map((c) => (
          <div className="stat" key={c.kind}>
            <b>{KIND_LABEL[c.kind ?? ""] ?? c.kind}</b>
            <span>{c.waiting} waiting</span>
            <span className={c.failed_24h ? "bad" : "muted"}>{c.failed_24h} failed today</span>
          </div>
        ))}
      </div>
      <table className="admin-table jobs">
        <thead><tr><th>What</th><th>Allotment</th><th>Status</th><th>When</th><th>Took</th></tr></thead>
        <tbody>
          {(data.jobs ?? []).map((j) => <JobRow key={`${j.kind}-${j.id}`} job={j} />)}
        </tbody>
      </table>
      {data.jobs?.length === 0 && <p className="muted">Nothing has run yet.</p>}
    </>
  );
}

function JobRow({ job }: { job: Job }) {
  const bad = job.status === "failed";
  return (
    <tr>
      <td>
        {job.label}
        <span className="muted"> · {KIND_LABEL[job.kind ?? ""] ?? job.kind}</span>
        {job.error && <div className="bad small">{job.error}</div>}
      </td>
      <td>{job.allotment_name ?? job.allotment_id}</td>
      <td className={bad ? "bad" : undefined}>{job.status}{job.stage ? ` (${job.stage})` : ""}</td>
      <td>{ago(job.created_at)}</td>
      <td>{duration(jobTime(job))}</td>
    </tr>
  );
}

const NO_FILTER: LogFilter = { level: "warning", service: "", q: "", request_id: "", task_id: "" };

function LogsTab() {
  const [filter, setFilter] = useState<LogFilter>(NO_FILTER);
  const [live, setLive] = useState(true);
  const logs = useAdminLogs(filter, live);
  const set = (patch: Partial<LogFilter>) => setFilter((f) => ({ ...f, ...patch }));
  const pages = logs.data?.pages ?? [];
  const entries = pages.flatMap((p) => p?.entries ?? []);
  const services = pages[0]?.services ?? [];
  return (
    <>
      <div className="toolbar">
        <input type="search" placeholder="Search the messages" aria-label="Search" value={filter.q} onChange={(e) => set({ q: e.target.value })} />
        <select aria-label="Level" value={filter.level} onChange={(e) => set({ level: e.target.value })}>
          <option value="">Everything</option>
          <option value="warning">Warnings and errors</option>
          <option value="error">Errors only</option>
        </select>
        <select aria-label="Service" value={filter.service} onChange={(e) => set({ service: e.target.value })}>
          <option value="">All services</option>
          {services.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="check"><input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> Refresh</label>
      </div>
      {(filter.request_id || filter.task_id) && (
        <p className="admin-chips">
          {filter.request_id && <button className="badge" onClick={() => set({ request_id: "" })}>request {filter.request_id.slice(0, 8)} ✕</button>}
          {filter.task_id && <button className="badge" onClick={() => set({ task_id: "" })}>task {filter.task_id.slice(0, 8)} ✕</button>}
        </p>
      )}
      {logs.isLoading && <p className="muted">Loading…</p>}
      {!logs.isLoading && entries.length === 0 && <p className="muted">No log lines match.</p>}
      <ul className="log-list">
        {entries.map((e) => <LogRow key={e.id} entry={e} onFilter={set} />)}
      </ul>
      {logs.hasNextPage && (
        <button onClick={() => logs.fetchNextPage()} disabled={logs.isFetchingNextPage}>
          {logs.isFetchingNextPage ? "Loading…" : "Load older"}
        </button>
      )}
    </>
  );
}

function LogRow({ entry, onFilter }: { entry: LogEntry; onFilter: (patch: Partial<LogFilter>) => void }) {
  const [first, ...rest] = (entry.event ?? "").split("\n");
  const hasMore = rest.length > 0 || (entry.data && Object.keys(entry.data).length > 0);
  return (
    <li className={`log log-${entry.level}`}>
      <div className="log-head">
        <time dateTime={entry.at} title={entry.at}>{new Date(entry.at ?? "").toLocaleString()}</time>
        <span className={`log-level level-${entry.level}`}>{entry.level}</span>
        <span className="muted">{entry.service}@{entry.host}</span>
        {entry.request_id && <button className="link" onClick={() => onFilter({ request_id: entry.request_id ?? "" })}>request</button>}
        {entry.task_id && <button className="link" onClick={() => onFilter({ task_id: entry.task_id ?? "" })}>task</button>}
      </div>
      {hasMore ? (
        <details>
          <summary>{first}</summary>
          {rest.length > 0 && <pre className="job-log">{rest.join("\n")}</pre>}
          {entry.data && Object.keys(entry.data).length > 0 && <pre className="job-log">{JSON.stringify(entry.data, null, 2)}</pre>}
        </details>
      ) : (
        <div>{first}</div>
      )}
    </li>
  );
}
