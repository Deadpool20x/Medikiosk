import Link from "next/link";
import { Icon } from "../components/icons";

export default function HomePage() {
  return (
    <main className="mk-home">
      <section className="mk-home__intro">
        <p className="mk-eyebrow">MediKiosk</p>
        <h1>Calm case-taking. Clear clinical review.</h1>
        <p>Choose the patient kiosk or the clinician workspace. All content is a synthetic demonstration.</p>
        <div className="mk-home__actions">
          <Link className="mk-button mk-button--primary" href="/patient">Patient kiosk <Icon className="mk-icon" name="arrow-right" /></Link>
          <Link className="mk-button mk-button--secondary" href="/doctor">Doctor workspace <Icon className="mk-icon" name="arrow-right" /></Link>
        </div>
      </section>
    </main>
  );
}
