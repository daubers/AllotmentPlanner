import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import MapEditor from "../map/MapEditor";

export default function AllotmentMap() {
  const id = Number(useParams().id);
  const allotment = useQuery({
    queryKey: ["allotment", id],
    queryFn: async () => (await api.GET("/api/v1/allotments/{allotment_id}", { params: { path: { allotment_id: id } } })).data,
  });

  if (allotment.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!allotment.data) return <main className="page"><p>Allotment not found. <Link to="/">Back to your allotments</Link></p></main>;

  const canEdit = allotment.data.role === "owner" || allotment.data.role === "editor";
  return (
    <div className="map-page">
      <header className="subbar">
        <Link to="/">← Allotments</Link>
        <strong>{allotment.data.name}</strong>
        <span className="badge">{allotment.data.role}</span>
      </header>
      <MapEditor allotmentId={id} canEdit={canEdit} />
    </div>
  );
}
