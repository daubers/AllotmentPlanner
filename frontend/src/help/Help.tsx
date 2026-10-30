import { Link, NavLink, useParams } from "react-router-dom";
import PublicLayout from "../public/PublicLayout";
import { usePageTitle } from "../public/usePageTitle";
import { TOPICS, topicBySlug } from "./content";

function Contents() {
  return (
    <nav className="help-nav" aria-label="Help topics">
      <NavLink to="/help" end>All topics</NavLink>
      {TOPICS.map((t) => <NavLink key={t.slug} to={`/help/${t.slug}`}>{t.title}</NavLink>)}
    </nav>
  );
}

export function HelpIndex() {
  usePageTitle("Help", "How to use Allotment Planner: the map, seeds and trays, photo maps, measuring and the phone app.");
  return (
    <PublicLayout>
      <div className="help">
        <Contents />
        <main className="prose">
          <h1>Help</h1>
          <p>How to get the most from Allotment Planner. Pick a topic.</p>
          <ul className="topics">
            {TOPICS.map((t) => (
              <li key={t.slug}>
                <Link to={`/help/${t.slug}`}>{t.title}</Link>
                <span className="muted">{t.summary}</span>
              </li>
            ))}
          </ul>
        </main>
      </div>
    </PublicLayout>
  );
}

export function HelpTopic() {
  const { topic } = useParams();
  const found = topicBySlug(topic);
  usePageTitle(found ? `${found.title} · Help` : "Help", found?.summary);
  if (!found) return <HelpIndex />;
  const at = TOPICS.indexOf(found);
  const prev = TOPICS[at - 1];
  const next = TOPICS[at + 1];
  return (
    <PublicLayout>
      <div className="help">
        <Contents />
        <main className="prose">
          <p className="muted"><Link to="/help">Help</Link> ›</p>
          <h1>{found.title}</h1>
          <found.Body />
          <p className="pager">
            {prev ? <Link to={`/help/${prev.slug}`}>‹ {prev.title}</Link> : <span />}
            {next ? <Link to={`/help/${next.slug}`}>{next.title} ›</Link> : <span />}
          </p>
        </main>
      </div>
    </PublicLayout>
  );
}
