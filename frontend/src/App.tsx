import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Allotments from "./pages/Allotments";
import Login from "./pages/Login";

// The map editor pulls in Leaflet + Geoman, so load it only when needed.
const AllotmentMap = lazy(() => import("./pages/AllotmentMap"));

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted centre">Loading…</p>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  const { user, logout } = useAuth();
  return (
    <>
      {user && (
        <nav className="topbar">
          <span>🌱 Allotment Planner</span>
          <span>
            {user.display_name} <button className="link" onClick={logout}>Sign out</button>
          </span>
        </nav>
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><Allotments /></Protected>} />
        <Route path="/allotments/:id" element={<Protected><Suspense fallback={<p className="muted centre">Loading map…</p>}><AllotmentMap /></Suspense></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
