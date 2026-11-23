import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { HelpIndex, HelpTopic } from "./help/Help";
import AccountPage from "./pages/AccountPage";
import AdminPage from "./pages/AdminPage";
import AllotmentLayout from "./pages/AllotmentLayout";
import Allotments from "./pages/Allotments";
import LayersPage from "./pages/LayersPage";
import Login from "./pages/Login";
import OidcCallback from "./pages/OidcCallback";
import NotesPage from "./pages/NotesPage";
import OverviewPage from "./pages/OverviewPage";
import PhotosPage from "./pages/PhotosPage";
import BedPage from "./pages/BedPage";
import BedsPage from "./pages/BedsPage";
import EquipmentItemPage from "./pages/EquipmentItemPage";
import EquipmentPage from "./pages/EquipmentPage";
import PlanPage from "./plan/PlanPage";
import PacketPage from "./pages/PacketPage";
import SeedsPage from "./pages/SeedsPage";
import SettingsPage from "./pages/SettingsPage";
import TasksPage from "./pages/TasksPage";
import TrayPage from "./pages/TrayPage";
import TraysPage from "./pages/TraysPage";
import TodayPage from "./pages/TodayPage";
import VisitsPage from "./pages/VisitsPage";
import Landing from "./public/Landing";
import Privacy from "./public/Privacy";

// The map editor pulls in Leaflet + Geoman, so load it only when needed.
const MapView = lazy(() => import("./pages/MapView"));

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted centre">Loading…</p>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

/** The front door: the sales page for visitors, the allotments list for people who are signed in. */
function Home() {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted centre">Loading…</p>;
  return user ? <Allotments /> : <Landing />;
}

export default function App() {
  const { user, logout } = useAuth();
  return (
    <>
      {user && (
        <nav className="topbar no-print">
          <span><Link to="/" className="plain">🌱 Allotment Planner</Link></span>
          <span>
            {user.is_admin && <Link to="/admin" className="plain">Admin</Link>} <Link to="/help" className="plain">Help</Link> <Link to="/account" className="plain">{user.display_name}</Link> <button className="link" onClick={logout}>Sign out</button>
          </span>
        </nav>
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<OidcCallback />} />
        <Route path="/" element={<Home />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
        <Route path="/account" element={<Protected><AccountPage /></Protected>} />
        <Route path="/help" element={<HelpIndex />} />
        <Route path="/help/:topic" element={<HelpTopic />} />
        <Route path="/allotments/:id" element={<Protected><AllotmentLayout /></Protected>}>
          <Route index element={<Suspense fallback={<p className="muted centre">Loading map…</p>}><MapView /></Suspense>} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="today" element={<TodayPage />} />
          <Route path="visits" element={<VisitsPage />} />
          <Route path="photos" element={<PhotosPage />} />
          <Route path="notes" element={<NotesPage />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="layers" element={<LayersPage />} />
          <Route path="seeds" element={<SeedsPage />} />
          <Route path="seeds/:packetId" element={<PacketPage />} />
          <Route path="plan" element={<PlanPage />} />
          <Route path="equipment" element={<EquipmentPage />} />
          <Route path="equipment/:equipmentId" element={<EquipmentItemPage />} />
          <Route path="beds" element={<BedsPage />} />
          <Route path="beds/:featureId" element={<BedPage />} />
          <Route path="trays" element={<TraysPage />} />
          <Route path="trays/:trayId" element={<TrayPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
