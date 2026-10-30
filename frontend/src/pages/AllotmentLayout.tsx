import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation, useOutletContext, useParams } from "react-router-dom";
import { api, type Allotment } from "../api/client";
import { groupFor, NAV } from "./nav";

export type AllotmentContext = { id: number; allotment: Allotment; canEdit: boolean };

export function useAllotment(): AllotmentContext {
  return useOutletContext<AllotmentContext>();
}

/** Shared header + data for everything under /allotments/:id. */
export default function AllotmentLayout() {
  const id = Number(useParams().id);
  const { pathname } = useLocation();
  const allotment = useQuery({
    queryKey: ["allotment", id],
    queryFn: async () =>
      (await api.GET("/api/v1/allotments/{allotment_id}", { params: { path: { allotment_id: id } } })).data,
  });

  if (allotment.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!allotment.data)
    return <main className="page"><p>Allotment not found. <Link to="/">Back to your allotments</Link></p></main>;

  const canEdit = allotment.data.role === "owner" || allotment.data.role === "editor";
  const active = groupFor(pathname);
  const group = NAV.find((g) => g.key === active);
  const context: AllotmentContext = { id, allotment: allotment.data, canEdit };
  return (
    <div className="shell">
      <header className="no-print">
        <div className="subbar">
          <Link to="/">← Allotments</Link>
          <strong>{allotment.data.name}</strong>
          <span className="badge">{allotment.data.role}</span>
          {canEdit && <NavLink to="settings" className="settings-link">Settings</NavLink>}
        </div>
        <nav className="groups" aria-label="Sections">
          {NAV.map((g) => (
            <NavLink key={g.key} to={g.pages[0].to} end={g.pages[0].end} className={g.key === active ? "active" : ""}>
              {g.label}
            </NavLink>
          ))}
        </nav>
        {group && (
          <nav className="pages" aria-label={`${group.label} pages`}>
            {group.pages.map((p) => (
              <NavLink key={p.to} to={p.to} end={p.end ?? false}>{p.label}</NavLink>
            ))}
          </nav>
        )}
      </header>
      <div className="shell-body">
        <Outlet context={context} />
      </div>
    </div>
  );
}
