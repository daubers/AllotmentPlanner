import { Link } from "react-router-dom";
import PublicLayout from "./PublicLayout";
import { SCREENS, screenUrl } from "./screens";
import { usePageTitle } from "./usePageTitle";
import { useRegistration } from "./useRegistrationOpen";

const SUMMARY = "Plan your allotment on a map, keep track of seeds and trays, and turn a walk round the plot into a map.";

function Feature({ title, shot, children, flip }: { title: string; shot: keyof typeof SCREENS; children: React.ReactNode; flip?: boolean }) {
  return (
    <section className={flip ? "feature flip" : "feature"}>
      <div className="feature-text">
        <h2>{title}</h2>
        {children}
      </div>
      <img className={shot === "phone" ? "shot phone" : "shot"} src={screenUrl(shot)} alt={SCREENS[shot].alt} loading="lazy" />
    </section>
  );
}

export default function Landing() {
  usePageTitle(null, SUMMARY);
  const registration = useRegistration();
  return (
    <PublicLayout>
      <main className="landing">
        <section className="hero">
          <h1>Your allotment, on one map.</h1>
          <p className="lead">{SUMMARY}</p>
          <div className="hero-actions">
            <Link to="/login" className="button">Sign in</Link>
            {registration === "open" && <Link to="/login?register=1" className="button secondary">Create account</Link>}
          </div>
          {registration === "invite" && <p className="muted">Accounts here are by invitation. If you were sent an invite link, open it to join.</p>}
        </section>

        <Feature title="Draw the plot" shot="map">
          <p>Sketch beds, paths, sheds, trees, water and the boundary over a street or satellite map. Name them, pin tasks to them, lock the ones that should not move, and undo a slip with Ctrl/⌘+Z.</p>
          <p><Link to="/help/map">How the map works</Link></p>
        </Feature>

        <Feature title="Let your photos do the mapping" shot="found" flip>
          <p>Walk round taking photos or a video. The service works out where each was taken, finds the beds, trees and sheds in them, and suggests shapes for your map. You check each suggestion against the photo, with the object outlined, before anything is added.</p>
          <p><Link to="/help/photo-maps">Photo maps and found items</Link></p>
        </Feature>

        <Feature title="Know what to sow, and when" shot="seeds">
          <p>Keep your seed packets, photograph the back of a new one to fill it in, and see what to sow this month. Record what is growing in each bed.</p>
          <p><Link to="/help/seeds-and-trays">Seeds, trays and beds</Link></p>
        </Feature>

        <Feature title="Follow every seed tray" shot="trays" flip>
          <p>See what you sowed in which cell, mark what has come up, and move seedlings into a bed when they are ready. It works on the phone without signal.</p>
        </Feature>

        <Feature title="Take it to the plot" shot="phone">
          <p>The Android phone app guides you through photographing the plot, measures real distances with a tape to correct the map, and queues everything to send when you have signal. It also lets you review what was found.</p>
          <p><Link to="/help/phone-app">About the phone app</Link></p>
        </Feature>

        <section className="own">
          <h2>Yours to run</h2>
          <p>Allotment Planner is self-hosted. Your plot, photos and locations stay on the server you use it on, with no advertising and no analytics. Read the <Link to="/privacy">privacy page</Link> for exactly what is kept and who sees it.</p>
          <div className="hero-actions">
            <Link to="/login" className="button">Sign in</Link>
            <Link to="/help" className="button secondary">Read the help</Link>
          </div>
        </section>
      </main>
    </PublicLayout>
  );
}
