# Screenshots for the landing page

The pictures on the public landing page live in `frontend/public/screens/` (`map`, `found`, `seeds`, `trays`, `phone`, all `.png`) and are listed, with their alt text, in `frontend/src/public/screens.ts`. A test checks that every one exists.

They are made from a throwaway **demo plot**, never from real data. To refresh them:

1. Start the dev stack (`make up`) so the API is on `localhost:8000`.
2. `python3 docs/screenshots/demo_seed.py > demo.json` registers a demo user and plot with beds, a path, a shed, a tree and tasks; `python3 docs/screenshots/demo_seed2.py` adds seed packets and a seed tray. (Adjust the `exec(...)`/`demo.json` paths if you run them from another folder.) Found items need a photo: upload any garden-like picture to the demo plot and add `MapSuggestion` rows whose `sightings` outline it (see the last step of the original change for the shape: `{media_id, outline: [[x, y]...], score, kind: "photo"}`).
3. For the phone picture run `EXPO_PUBLIC_DEMO=1 npx expo start --web --port 8099` in `mobile/`.
4. `docs/screenshots/capture.cjs` takes the shots with the repo's Playwright image, for example
   `docker run --rm --network <project>_default --add-host host.docker.internal:host-gateway -v $PWD/e2e/node_modules:/e2e/node_modules:ro -v <dir with demo.json and capture.cjs>:/shots -w /shots -e NODE_PATH=/e2e/node_modules mcr.microsoft.com/playwright:v1.64.1-noble node capture.cjs`
   (it writes into `/shots/demo_shots/`; copy the results into `frontend/public/screens/`).
5. **Delete the demo plot and user afterwards** (delete the allotment in the app so its files go too).

Use light theme, a 1280x800 window for web pages and 390 wide for the phone.
