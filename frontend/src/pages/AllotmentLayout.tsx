import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";
import { api, type Allotment } from "../api/client";

export type AllotmentContext = { id: number; allotment: Allotment; canEdit: boolean };

export function useAllotment(): AllotmentContext {
  return useOutletContext<AllotmentContext>();
}

/** Shared header + data for everything under /allotments/:id. */
export default function AllotmentLayout() {
  const id = Number(useParams().id);
  const allotment = useQuery({
    queryKey: ["allotment", id],
    queryFn: async () =>
      (await api.GET("/api/v1/allotments/{allotment_id}", { params: { path: { allotment_id: id } } })).data,
  });

  if (allotment.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!allotment.data)
    return <main className="page"><p>Allotment not found. <Link to="/">Back to your allotments</Link></p></main>;

  const canEdit = allotment.data.role === "owner" || allotment.data.role === "editor";
  const context: AllotmentContext = { id, allotment: allotment.data, canEdit };
  return (
    <div className="shell">
      <header className="subbar">
        <Link to="/">← Allotments</Link>
        <strong>{allotment.data.name}</strong>
        <span className="badge">{allotment.data.role}</span>
        <nav className="tabs">
          <NavLink to="" end>Map</NavLink>
          <NavLink to="tasks">Tasks</NavLink>
        </nav>
      </header>
      <div className="shell-body">
        <Outlet context={context} />
      </div>
    </div>
  );
}
