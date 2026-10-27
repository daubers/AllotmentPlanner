import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function Allotments() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const list = useQuery({
    queryKey: ["allotments"],
    queryFn: async () => (await api.GET("/api/v1/allotments")).data ?? [],
  });
  const create = useMutation({
    mutationFn: async (n: string) => api.POST("/api/v1/allotments", { body: { name: n } }),
    onSuccess: () => { setName(""); qc.invalidateQueries({ queryKey: ["allotments"] }); },
  });

  return (
    <main className="page">
      <h1>Your allotments</h1>
      {list.isLoading && <p className="muted">Loading…</p>}
      {list.data?.length === 0 && <p className="muted">No allotments yet. Create your first one below.</p>}
      <ul className="cards">
        {list.data?.map((a) => (
          <li key={a.id}>
            <Link to={`/allotments/${a.id}`}>
              <strong>{a.name}</strong>
              <span className="badge">{a.role}</span>
            </Link>
          </li>
        ))}
      </ul>
      <form className="inline" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(name.trim()); }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New allotment name" aria-label="New allotment name" maxLength={120} />
        <button type="submit" disabled={create.isPending}>Create</button>
      </form>
    </main>
  );
}
