import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import AllotmentLayout from "./pages/AllotmentLayout";
import Allotments from "./pages/Allotments";
import LayersPage from "./pages/LayersPage";
import Login from "./pages/Login";
import OverviewPage from "./pages/OverviewPage";
import PhotosPage from "./pages/PhotosPage";
import PacketPage from "./pages/PacketPage";
import SeedsPage from "./pages/SeedsPage";
import SettingsPage from "./pages/SettingsPage";
import TasksPage from "./pages/TasksPage";
import TrayPage from "./pages/TrayPage";
import TraysPage from "./pages/TraysPage";
import TodayPage from "./pages/TodayPage";

// The map editor pulls in Leaflet + Geoman, so load it only when needed.
const MapView = lazy(() => import("./pages/MapView"));

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
        <nav className="topbar no-print">
          <span>🌱 Allotment Planner</span>
          <span>
            {user.display_name} <button className="link" onClick={logout}>Sign out</button>
          </span>
        </nav>
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><Allotments /></Protected>} />
        <Route path="/allotments/:id" element={<Protected><AllotmentLayout /></Protected>}>
          <Route index element={<Suspense fallback={<p className="muted centre">Loading map…</p>}><MapView /></Suspense>} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="today" element={<TodayPage />} />
          <Route path="photos" element={<PhotosPage />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="layers" element={<LayersPage />} />
          <Route path="seeds" element={<SeedsPage />} />
          <Route path="seeds/:packetId" element={<PacketPage />} />
          <Route path="trays" element={<TraysPage />} />
          <Route path="trays/:trayId" element={<TrayPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
