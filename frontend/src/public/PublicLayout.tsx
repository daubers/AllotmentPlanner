import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth";
import { CONTACT_EMAIL, SITE_NAME } from "./site";
import { useRegistration } from "./useRegistrationOpen";

/** Header and footer shared by the pages anyone can read: landing, privacy and help. */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const registration = useRegistration();
  return (
    <div className="public">
      {!user && (
      <header className="public-bar">
        <Link to="/" className="brand">
          <img src="/logo.svg" alt="" width={28} height={28} />
          <span>{SITE_NAME}</span>
        </Link>
        <nav aria-label="Main">
          <NavLink to="/help">Help</NavLink>
          <Link to="/login">Sign in</Link>
          {registration === "open" && <Link to="/login?register=1" className="button">Create account</Link>}
        </nav>
      </header>
      )}
      {children}
      <footer className="public-foot">
        <nav aria-label="Footer">
          <Link to="/help">Help</Link>
          <Link to="/privacy">Privacy</Link>
          <a href={`mailto:${CONTACT_EMAIL}`}>Contact</a>
        </nav>
        <p className="muted">{SITE_NAME} is self-hosted: your plot and photos stay on the server you use it on.</p>
      </footer>
    </div>
  );
}
