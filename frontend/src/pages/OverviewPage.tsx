import { Link } from "react-router-dom";
import { useOverview } from "../overview/hooks";
import { dayLabel, level, streakText, weekColumns, weekHeadline } from "../overview/summary";
import { useAllotment } from "./AllotmentLayout";

export default function OverviewPage() {
  const { id } = useAllotment();
  const { data, isLoading } = useOverview(id);
  if (isLoading) return <main className="page wide"><p className="muted">Loading…</p></main>;
  if (!data) return <main className="page wide"><p>Couldn't load the overview.</p></main>;

  const max = Math.max(0, ...(data.days ?? []).map((d) => d.total ?? 0));
  const columns = weekColumns(data.days ?? []);
  const t = data.totals!;
  return (
    <main className="page wide overview">
      <section className="hero">
        <h1>{weekHeadline(data.this_week!, data.last_week!)}</h1>
        <p className="muted">{streakText(data.streak!.current ?? 0, data.streak!.longest ?? 0)}</p>
      </section>

      <section className="stats" aria-label="All time">
        <div><strong>{t.tasks_done}</strong><span>{t.tasks_done === 1 ? "task" : "tasks"} done</span></div>
        <div><strong>{t.photos_added}</strong><span>{t.photos_added === 1 ? "photo" : "photos"}</span></div>
        <div><strong>{t.map_edits}</strong><span>{t.map_edits === 1 ? "map edit" : "map edits"}</span></div>
        <div><strong>{t.active_days}</strong><span>{t.active_days === 1 ? "active day" : "active days"}</span></div>
        <div><strong>{data.open_tasks}</strong><span>still to do</span></div>
      </section>

      <section>
        <h2>Activity</h2>
        <div className="heatmap" role="img" aria-label={`Activity over the last ${data.days?.length} days`}>
          {columns.map((week, i) => (
            <div className="heat-col" key={i}>
              {week.map((d, j) =>
                d ? <span key={d.date} className={`heat l${level(d.total ?? 0, max)}`} title={dayLabel(d)} /> : <span key={j} className="heat blank" />,
              )}
            </div>
          ))}
        </div>
        <p className="legend muted">Less {[0, 1, 2, 3, 4].map((n) => <span key={n} className={`heat l${n}`} />)} More</p>
      </section>

      <section>
        <h2>Recently done</h2>
        {data.recent_done?.length ? (
          <ul className="done-list">
            {data.recent_done.map((task) => (
              <li key={String(task.id)}>✓ {String(task.title)} <span className="muted">{String(task.completed_at).slice(0, 10)}</span></li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing completed yet. <Link to="../tasks">Add a job</Link>.</p>
        )}
      </section>

      <section>
        <h2>Latest photos</h2>
        {data.recent_photos?.length ? (
          <ul className="grid">
            {data.recent_photos.map((m) => (
              <li key={m.id}>
                <Link to="../photos" className="tile">{m.thumb_url ? <img src={m.thumb_url} alt={m.caption || m.filename} loading="lazy" /> : null}</Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No photos yet. <Link to="../photos">Upload one</Link> to start the timeline.</p>
        )}
      </section>
    </main>
  );
}
