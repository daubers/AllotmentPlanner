import { Link } from "react-router-dom";

export type Topic = { slug: string; title: string; summary: string; Body: () => React.ReactElement };

function GettingStarted() {
  return (
    <>
      <h2>Signing in</h2>
      <p>
        Use <Link to="/login">Sign in</Link> with your email and password. If the server is open to everyone you can
        also create an account from the same page. On a server that is by invitation only, an owner of an allotment
        sends you an invite link: open it, choose a name and password, and you are added to that allotment.
      </p>
      <h2>Your first allotment</h2>
      <p>
        After signing in, the first page lists your allotments. Type a name under <em>New allotment name</em> and
        choose <em>Create</em>, then open it. The menu along the top is grouped by what you are doing:
        <strong> Plot</strong> (Map, Map from photos), <strong>Grow</strong> (Seeds, Trays, Beds, Plan, Equipment),
        <strong>Work</strong> (Today, Tasks) and <strong>Record</strong> (Photos, Overview). Choose a group to see its pages;
        Settings is at the top right.
      </p>
      <h2>Your data and your account</h2>
      <p>
        Open <Link to="/account">Your account</Link> (your name at the top). <em>Download my data</em> prepares a zip of
        your account details, everything you added and the photos and videos you uploaded; it is built in the
        background, so give it a few minutes if you have a lot of photos, and the link works for two days.
        <em> Delete my account</em> removes your account and any allotment that only you belong to, with its photos.
        If you are the only owner of an allotment that other people share, make one of them an owner first (or delete the
        allotment); the page tells you which. Things you added to an allotment shared with others stay there, no longer
        linked to you. If you signed up with a provider and have no password, you confirm with that provider.
      </p>
      <h2>Who can do what</h2>
      <ul>
        <li><strong>Owner</strong> can do everything, including inviting people and changing settings.</li>
        <li><strong>Editor</strong> can draw on the map, add tasks, photos, seeds and trays, and build maps from photos.</li>
        <li><strong>Viewer</strong> can look but not change anything.</li>
      </ul>
      <h2>Inviting someone</h2>
      <p>
        Owners open <em>Settings</em> and use <em>Invite someone</em>: enter their email and choose a role, then send
        them the link it makes. The link works for that email address only and expires after a few days.
      </p>
    </>
  );
}

function TheMap() {
  return (
    <>
      <h2>Drawing</h2>
      <p>
        Use the toolbar on the left of the map to draw a shape (area, line, circle or marker). When you finish, it is
        saved straight away and appears under <em>Map features</em> in the side panel. Give it a name and a kind: bed,
        path, shed, tree, water, compost, boundary or other. The kind sets its colour and its place in the stacking
        order (see below).
      </p>
      <p>The toolbar also has edit, drag and delete modes. Switch the street and satellite views from the control at the top right.</p>
      <h2>Keeping things where you put them</h2>
      <ul>
        <li><strong>Lock position.</strong> Select a shape and tick <em>Lock position</em>. It shows a 🔒 in the list, and can no longer be dragged, reshaped or deleted, here or from the phone, until you untick it. You can still rename it and change its kind.</li>
        <li><strong>Undo and redo.</strong> Use the <em>Undo</em> and <em>Redo</em> buttons above the list, or Ctrl/⌘+Z and Ctrl/⌘+Shift+Z. They cover moving and reshaping, adding, deleting, renaming, changing kind, locking and reordering, and each one is saved. The history lasts until you reload the page.</li>
      </ul>
      <h2>Shapes on top of shapes</h2>
      <p>
        Shapes are drawn from the bottom up: boundaries, then water, paths, beds, compost, other things, sheds and
        trees. So a bed inside a boundary can always be clicked. To change it, select a shape and use{" "}
        <em>Bring to front</em> or <em>Send to back</em>.
      </p>
      <p>To select something hidden underneath another shape, hold Alt (Option on a Mac) and click: each click moves down to the next shape under the pointer. You can also pick any shape from the list.</p>
      <h2>Tasks on the map</h2>
      <p>Select a shape and add a task under <em>Tasks here</em>; it shows as a 📌 on the map. The <em>Tasks</em> and <em>Today</em> pages (in <em>Work</em>) list them all, and Today prints as a clean list to take to the plot. On screen you can tick jobs off on Today as you do them (they stay on the page, struck through, until you change the date); the printed list keeps empty boxes to tick with a pen. Each heading links to its bed or seed tray.</p>
      <h2>Day lists</h2>
      <p>
        A day list is a hand-picked set of jobs, like <em>Saturday morning</em> or <em>Watering round</em>. On <em>Today</em> choose
        <em> Manage lists</em> to make one (give it a date if you like), then open <em>Add jobs to…</em> to tick the jobs to put on it.
        Choosing the list in the <em>List</em> box turns the page into that list&rsquo;s todo sheet: tick jobs off on screen, take one off
        the list with ✕ (the job itself is kept), or press <em>Print</em> for a paper copy. Jobs you finish stay on the sheet, struck
        through. Everyone in the allotment sees the same lists.
      </p>
      <p>
        On the <em>Tasks</em> page, the 📋 box on a task adds it to a list (or makes a new one), and a list you used last gets a quick
        <em> ＋ list name</em> button on every task. In <em>Select</em> mode, tick several tasks and use <em>Add to list</em>. A task shows
        which lists it is on, and its dialog lets you take it off.
      </p>
      <h2>Adding and editing tasks</h2>
      <p>
        Press <em>+ New task</em> on the <em>Tasks</em> page, or <em>More…</em> beside a shape on the map. A task can have notes,
        a due date, a priority, someone it is assigned to, a place (a shape on the map, a seed tray or something growing) and a
        repeat. Click a task&rsquo;s title to change or delete it. When you finish a repeating task the next one is due after
        the later of its old date and today, so a late job does not come back already overdue.
      </p>
      <h2>Tasks suggested from sow dates</h2>
      <p>
        On a seed tray, or on something growing in a bed, press <em>Suggest tasks</em>. From the seed packet&rsquo;s germination
        and maturity days and its plant-out and harvest months you get a list: check germination, prick out, harden off, plant
        out, thin and harvest, each with a date. <em>Add</em> puts them all on your task list, pinned to that tray or planting.
        Steps whose date has already passed are left out, and pressing it again never adds the same task twice.
      </p>
      <h2>Finding tasks</h2>
      <p>
        Above the list, search the titles and notes, show just your own jobs (<em>Mine</em>), one person&rsquo;s, or the
        unassigned ones, and narrow by priority, status or place. The page address keeps your choices, so you can bookmark a
        view such as &ldquo;my high-priority jobs&rdquo;. Use the 📅 menu on a task to move it to tomorrow or next week, or
        press <em>Select</em> to tick several and complete, reschedule or delete them together.
      </p>
    </>
  );
}

function SeedsAndTrays() {
  return (
    <>
      <h2>Seed packets</h2>
      <p>
        The <em>Seeds</em> page (in <em>Grow</em>) is your library. Add a packet by hand, or photograph the back of a packet and let the
        service read it: it makes a draft that says what it could not find, so you can correct it and save it to the
        library. Each packet has a calendar of when to sow indoors and outdoors, and the list can show only what to sow this month.
      </p>
      <h2>Trays</h2>
      <p>
        <em>Trays</em> shows a grid of cells. Select cells (or a whole row or column), sow a packet into them, and
        later mark them <em>Came up</em> or <em>Failed</em>. To correct what was sown, select the cells and change the seed, the number of seeds, the sown date or the note, then press <em>Sow / update</em>; a field you leave blank is left as it is.  Each kind of seed has its own colour. Photos of a tray stay linked to it.
      </p>
      <h2>Beds and what is growing</h2>
      <p>
        <em>Beds</em> lists the shapes you drew as beds. Open one to see what is growing in it, mark each planting's
        stage, and draw a planting area inside the bed. Seedlings from a tray can be planted out into a bed. On the phone, the
        same screens work without signal and send their changes when you are back in range.
      </p>
    </>
  );
}

function Planning() {
  return (
    <>
      <h2>The plan</h2>
      <p>
        <em>Plan</em> (in <em>Grow</em>) shows what you mean to grow in each bed over twelve months. Use the arrows to move the window a
        month at a time, and the <em>Bed</em> list to look at one bed. Each crop is a bar: it starts when the crop goes into the bed and
        ends when the bed is free again. A pale lead-in before a bar is time in a seed tray.
      </p>
      <h2>Adding a crop</h2>
      <p>
        Press <em>Add crop</em> on a bed. Choose one of your seed packets or one of the built-in crops, and the dates fill in from its
        sowing months and days to harvest (change them freely). Say how much space it takes, in square metres or as a share of the bed.
        If you give the number of plants, the form suggests the space they need from the plant and row spacing; the figure is
        approximate. Tick <em>Repeat as a succession</em> to plan several sowings a set number of days apart.
      </p>
      <h2>Tasks from the plan</h2>
      <p>
        Under the beds, <em>Tasks from the plan</em> lists the jobs your plan implies: sowing each crop, planting out a transplant, and
        clearing the bed when a crop ends (naming the crop that follows it). Untick any you do not want and press <em>Add</em>; they
        appear on the Tasks and Today pages. If you later change the plan, tasks you have not started are marked out of date and
        <em>Update</em> brings them in line (tasks you have started or finished are never changed). For watering, weeding or feeding,
        press <em>Add a repeating job</em> to make a task every few days, weeks or months until a date you choose.
      </p>
      <h2>Is the bed full?</h2>
      <p>
        The <em>Space used</em> row shows how much of the bed is taken each month. A month turns red, and the bed shows a warning, when
        the crops planned together need more than the bed has. That is only a warning: you can keep the plan as it is. One crop ending
        on the day the next one starts is not a clash. A bed drawn without an area (a point or a line) cannot be checked.
      </p>
    </>
  );
}

function Equipment() {
  return (
    <>
      <h2>Your equipment</h2>
      <p>
        <em>Equipment</em> (in <em>Grow</em>) lists the tools and kit you have. Add an item with a name, the kind of thing it is (spade,
        dibber, cloche) and how many you own. Open it to say where it is kept, to mark it <em>Out of action</em> when it is broken or lent
        out, and to add notes.
      </p>
      <h2>Equipment on a job</h2>
      <p>
        When you add or edit a job, the <em>Equipment</em> row suggests what you own that it probably needs (digging suggests a spade, sowing
        a dibber), as dashed chips: press one to add it, or press <em>✕</em> on any chip to take it off. Suggestions come from the words in
        the title and notes and, for jobs made from a tray, a planting or the plan, from what kind of job it is. Nothing is added unless you
        choose it. Jobs show the tools they need on the Tasks and Today pages.
      </p>
      <h2>What to bring on a visit</h2>
      <p>
        A planned visit lists the equipment its jobs need under <em>Equipment to bring</em>. A job with no tools of its own borrows the
        first couple of suggestions once the visit is saved. Add anything extra, or take off what you already have there. The list appears in
        the calendar entry (<em>Bring: …</em>), the Today sheet (<em>Take with you</em>) and on the phone.
      </p>
      <h2>Used for</h2>
      <p>
        Under <em>Used for</em>, list the words that should make an item suggested for a job (for example <em>dig, trench</em> on a border
        spade). The kind already covers the common cases, so leave it blank unless you want your own rules.
      </p>
    </>
  );
}

function PhotoMaps() {
  return (
    <>
      <h2>What you need</h2>
      <ul>
        <li>At least 5 photos (a video counts as about one image per second) that overlap each other, taken while walking around the plot.</li>
        <li>At least 3 photos with a location. Photos from the phone app carry the phone's location and compass heading. A video has only one location, so it cannot place the map on its own.</li>
        <li>Take a step or two between photos: pictures from one spot cannot be joined up.</li>
      </ul>
      <h2>Building a map</h2>
      <p>
        Open <em>Map from photos</em> (in the <em>Plot</em> group). Choose what to make (the objects found in your photos, and/or a stitched
        photo overlay), whether you took the photos looking across the plot or straight down, and the camera height. By default every
        finished photo and video is used; choose <em>pick which</em> to use only some. Optionally add a GPX file of a walk round the edge of the plot to give the map its boundary, and check the outline preview. Then start the job. It runs in the background and shows its stages and a log.
      </p>
      <h2>Reviewing what was found</h2>
      <p>
        When it finishes, the suggestions appear in the <em>Found in your photos</em> panel on the map and as
        footprints on the map itself. Each row shows the photos it was seen in with the object outlined. Click a photo to enlarge it,
        then check the outline is on the right thing. You can rename a suggestion, change its kind, and drag its footprint into place
        (the panel shows when the change is saved). Tick the ones you want and add them to the map; dismiss the rest. Nothing reaches the map until you accept it.
      </p>
      <p>On the phone app, the home screen offers <em>Review what was found</em> with the same photos, outlines, Add and Dismiss.</p>
      <h2>Good to know</h2>
      <ul>
        <li>If the same photo or video was uploaded twice, the second copy is left out and the job log says so.</li>
        <li>Suggestions made before photo review existed have no photos to show.</li>
        <li>Video frames only show in the review when the service kept a picture of that frame (jobs run since version 0.4.3).</li>
      </ul>
    </>
  );
}

function Measuring() {
  return (
    <>
      <p>
        Drawn shapes are only as accurate as your clicking. Measure with a tape to make the map true to size. This is
        done on the phone, with <em>Measure the plot</em>.
      </p>
      <h2>The checklist</h2>
      <p>
        <em>Make the checklist</em> (or <em>Update from the map</em>) lists the distances to take. For a shape with n
        corners that is each side plus a diagonal from corner 1 to every non-neighbouring corner, which fixes the shape
        exactly. A line needs one distance per segment, and a circle its radius.
      </p>
      <h2>Taking a measurement</h2>
      <p>
        Each row shows a sketch with the two corners to measure drawn bold. Type the distance as <code>3.2</code>,{" "}
        <code>320cm</code>, <code>10ft 6in</code> or <code>10'6"</code>, then choose <em>Save and next</em>. It works without signal.
      </p>
      <h2>Applying</h2>
      <p>
        <em>Apply to map</em> previews the correction, with the drawn outline dashed and the corrected one solid,
        how far each corner moves, and warnings if a measurement disagrees with the others (probably a misread). Applying is all or
        nothing. The shape stays where it was drawn: it is not turned, shifted or mirrored. An extra measurement beyond the minimum lets the
        fit check your others.
      </p>
    </>
  );
}

function PhoneApp() {
  return (
    <>
      <h2>Getting the app</h2>
      <p>
        The phone app is currently installed from a file rather than from a store. Ask whoever runs your server for the
        latest Android APK, open it on the phone and allow installing from that source. It will be available from the Play Store in future.
      </p>
      <h2>Signing in</h2>
      <p>
        Enter the server address (for example <code>https://plot.example.com</code>, or the address of the computer on your home
        network), then your email and password. The address is remembered. If you belong to more than one allotment, use <em>Switch</em> on the home screen.
      </p>
      <h2>Photographing the plot</h2>
      <p>
        <em>Photograph the plot</em> opens the camera. It records where you are, which way the camera faces and how it is tilted for each
        shot, and coaches you as you go: wait for a good location, take a step between photos, and keep the camera near level. At the end it
        summarises the walk, and offers <em>Build a map from this walk</em> once every photo has reached the server.
      </p>
      <h2>No signal?</h2>
      <p>
        Everything you do is saved on the phone first and sent when there is signal, oldest first, retrying
        automatically. A banner on the home screen shows what is waiting; open it to retry or discard anything the server refused. Saving a
        seed packet, making the measuring checklist, and reviewing found items do need a connection.
      </p>
      <h2>Your account</h2>
      <p><em>Account</em> on the home screen lets you download a copy of your data and delete your account, the same as on the web (see <Link to="/help/getting-started">getting started</Link>).</p>
      <h2>What the app can ask for</h2>
      <p>The camera, your location while the app is open, and the motion sensors. See <Link to="/privacy">privacy</Link> for how they are used.</p>
    </>
  );
}

function Sharing() {
  return (
    <>
      <h2>Sharing an allotment</h2>
      <p>Invite people from <em>Settings</em> (see <Link to="/help/getting-started">getting started</Link>). Everyone you invite sees the same map, tasks, photos, seeds and trays; what they can change depends on their role. The overview and activity log show who did what.</p>
      <h2>Posting to Mastodon</h2>
      <p>
        In <em>Settings</em> an owner can connect a Mastodon account, choose whether tasks, photos and a daily digest are
        posted, and pick the visibility (unlisted by default). Nothing is posted until you switch it on. Photos posted to Mastodon
        can show where they were taken, so check the visibility first.
      </p>
      <h2>The photo timeline and overview</h2>
      <p><em>Photos</em> shows everything uploaded by day, with a before/after slider. <em>Overview</em> summarises what you have done: a look-back at the work on the plot.</p>
    </>
  );
}

function Troubleshooting() {
  return (
    <>
      <h2>My map job found nothing</h2>
      <ul>
        <li><strong>The same video twice.</strong> Two copies of a recording make the map fall apart. Since version 0.5.1 repeated uploads are left out automatically; before that, delete the extra copy and run it again.</li>
        <li><strong>Too few overlapping photos.</strong> Walk more slowly, take a step between photos, and face different directions so each part of the plot is seen from several places.</li>
        <li><strong>Too few locations.</strong> At least 3 photos must have a location. Check location was on when the photos were taken.</li>
        <li>Open the job's log on the <em>Map from photos</em> page. A line such as "N of M detections could be put on the ground" says how many things were seen but could not be placed.</li>
      </ul>
      <h2>"Only 0 of 40 photo positions are inside the GPX boundary"</h2>
      <p>The boundary from your GPX trace and the photos disagree about where the plot is by more than a few metres. Check the GPX is of this plot, or leave the boundary out.</p>
      <h2>An upload is stuck on the phone</h2>
      <p>Open the sending screen from the banner on the home screen. Retry it when you have signal; if the server refused it, the reason is shown next to it.</p>
      <h2>I can't move or delete a shape</h2>
      <p>It may be locked (look for 🔒). Select it and untick <em>Lock position</em>.</p>
      <h2>I clicked the wrong shape</h2>
      <p>Hold Alt (Option on a Mac) and click again to move down to the shape underneath, or choose it from the list.</p>
      <h2>Still stuck?</h2>
      <p>Ask whoever runs your server, or see <Link to="/privacy">the privacy page</Link> for the contact for this one.</p>
    </>
  );
}

export const TOPICS: Topic[] = [
  { slug: "getting-started", title: "Getting started", summary: "Sign in, create an allotment, roles and invitations.", Body: GettingStarted },
  { slug: "map", title: "The map", summary: "Drawing, locking, undo, and shapes on top of shapes.", Body: TheMap },
  { slug: "seeds-and-trays", title: "Seeds, trays and beds", summary: "Packets, the sowing calendar, seed trays and what is growing.", Body: SeedsAndTrays },
  { slug: "planning", title: "Planning a year", summary: "Plan crops per bed, with space and successions.", Body: Planning },
  { slug: "equipment", title: "Equipment", summary: "The tools and kit you own, and where they are kept.", Body: Equipment },
  { slug: "photo-maps", title: "Photo maps and found items", summary: "Build a map from photos and video, then review what was found.", Body: PhotoMaps },
  { slug: "measuring", title: "Measuring the plot", summary: "Correct the map to real sizes with a tape measure.", Body: Measuring },
  { slug: "phone-app", title: "The phone app", summary: "Install it, photograph the plot, and work without signal.", Body: PhoneApp },
  { slug: "sharing", title: "Sharing and Mastodon", summary: "Invite people, post progress, the photo timeline.", Body: Sharing },
  { slug: "troubleshooting", title: "Troubleshooting", summary: "When a job finds nothing, or something will not move.", Body: Troubleshooting },
];

export const topicBySlug = (slug: string | undefined) => TOPICS.find((t) => t.slug === slug);
