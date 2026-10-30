import { Link } from "react-router-dom";
import PublicLayout from "./PublicLayout";
import { CONTACT_EMAIL, PRIVACY_UPDATED, SITE_NAME } from "./site";
import { usePageTitle } from "./usePageTitle";

export default function Privacy() {
  usePageTitle("Privacy", `What ${SITE_NAME} stores about you and your plot, who can see it, and how to have it removed.`);
  return (
    <PublicLayout>
      <main className="page prose">
        <h1>Privacy</h1>
        <p className="muted">Last updated {PRIVACY_UPDATED}.</p>
        <p>
          {SITE_NAME} is a self-hosted service for planning an allotment. This page says what it keeps, what it
          sends elsewhere, and how to get your data removed. It is written in plain language on purpose. Questions
          go to <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>

        <h2>Who is responsible</h2>
        <p>
          The person who runs the server you sign in to is responsible for the data on it. For the server this page
          is served from, that is the contact above. If you use the phone app with a server run by someone else, that
          person is the one to ask, and their privacy page (this one, if they have not changed it) applies.
        </p>

        <h2>What is stored</h2>
        <ul>
          <li><strong>Your account:</strong> your email address, the name you gave, and a hashed password (the password itself is never stored).</li>
          <li><strong>Your plot:</strong> the shapes you draw, their names, tasks, seed packets, trays, plantings and measurements. Other people on an allotment you share can see these, according to the role you gave them (owner, editor or viewer).</li>
          <li><strong>Photos and videos you upload:</strong> the files, and the details the camera recorded in them: when they were taken and, if location was on, where. This is often your plot, which may be at or near where you live.</li>
          <li><strong>Maps made from your photos:</strong> pictures cut from your photos and the outlines of what was found in them.</li>
          <li><strong>An activity log:</strong> what was added or changed on an allotment, and by which member, so a shared plot has a history.</li>
          <li><strong>Mastodon (optional):</strong> if you connect an account, the instance address and an access token, which is stored encrypted. It is used only to post what you have switched on.</li>
        </ul>

        <h2>The phone app</h2>
        <p>The Android app asks for three permissions, each only for what it says:</p>
        <ul>
          <li><strong>Camera</strong> to photograph your plot and seed packets.</li>
          <li><strong>Location, while the app is open</strong> to record where each photo was taken so a map can be built.</li>
          <li><strong>Motion sensors</strong> to check how level the phone is held.</li>
        </ul>
        <p>
          The app talks only to the server address you type in. It keeps your sign-in in the phone's secure storage
          and a queue of things waiting to be sent in a small local database. Photos are copied into the app's own
          storage and removed once they have been sent.
        </p>

        <h2>Who else gets anything</h2>
        <ul>
          <li><strong>Map pictures.</strong> The map in your browser loads street tiles from OpenStreetMap and, if you choose the satellite view, from Esri. Their servers see your IP address and which part of the world you are looking at. Nothing else is sent, and your shapes and photos are not sent to them.</li>
          <li><strong>Mastodon.</strong> Only if you connect it: the posts you switch on go to the instance you chose, with the visibility you chose. Treat anything posted as visible to whoever that setting allows. Original photo files keep the location the camera recorded.</li>
          <li><strong>Recognition models.</strong> The server downloads the models that recognise objects in photos from Hugging Face the first time it needs them. Your photos are processed on the server and are not sent out.</li>
        </ul>
        <p>There is no advertising, no analytics, no tracking, and no third-party scripts or fonts on these pages or in the app.</p>

        <h2>Cookies and browser storage</h2>
        <p>No cookies are used. When you sign in, the web app keeps your sign-in tokens in your browser's local storage so you stay signed in; signing out removes them.</p>

        <h2>Keeping it safe</h2>
        <p>
          Passwords are hashed. Mastodon tokens are encrypted. Photos are only served through short-lived signed
          links, to people who are members of the allotment. The app can be used over plain HTTP so that it works on
          a home network, but anything that crosses the internet should be served over HTTPS, and the operator of a
          public server should always set that up.
        </p>

        <h2>Keeping and deleting your data</h2>
        <p>
          Your data is kept until it is deleted; nothing expires on its own. In the app you can delete photos and
          videos, remove members, disconnect Mastodon, and delete an allotment, which removes everything on it.
          Deleting your whole account, and getting a copy of your data, are not yet buttons in the app: email{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> from the address on your account and it will be
          done by hand. Self-service deletion and export are planned.
        </p>

        <h2>Children</h2>
        <p>This service is not aimed at children, and does not knowingly collect their data.</p>

        <h2>Changes</h2>
        <p>If this page changes in a way that matters, the date at the top changes with it. See also the <Link to="/help">help pages</Link> for how each feature works.</p>
      </main>
    </PublicLayout>
  );
}
