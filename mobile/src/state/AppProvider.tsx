import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { AppState, Platform } from "react-native";
import { createApi, type Api } from "../api/client";
import { Session } from "../auth/session";
import { secureStore } from "../native/secureStore";
import { makeHandlers } from "../queue/handlers";
import { removeFile, uploadFile } from "../queue/nativeUpload";
import { JobQueue, MemoryJobStore, type QueueState } from "../queue/queue";
import { SqliteJobStore } from "../queue/sqliteStore";

const ALLOTMENT_KEY = "allotment.current";
const RUN_EVERY_MS = 15_000;

type AppContextValue = {
  session: Session;
  queue: JobQueue;
  api: Api;
  signedIn: boolean;
  allotmentId: number | null;
  chooseAllotment: (id: number) => void;
};

const AppContext = createContext<AppContextValue | null>(null);
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}

export function useQueueState(): QueueState {
  const { queue } = useApp();
  const [snapshot, setSnapshot] = useState(queue.state());
  useEffect(() => queue.subscribe(() => setSnapshot(queue.state())), [queue]);
  return snapshot;
}

type Booted = { session: Session; queue: JobQueue };

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [booted, setBooted] = useState<Booted | null>(null);
  const [allotmentId, setAllotmentId] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      const session = new Session(secureStore);
      await session.load();
      // The browser preview has no SQLite; its queue lives in memory only.
      const store = Platform.OS === "web" ? new MemoryJobStore() : await SqliteJobStore.open();
      const queue = new JobQueue(store, makeHandlers({ session, uploadFile, removeFile }));
      const saved = await secureStore.get(ALLOTMENT_KEY);
      if (saved) setAllotmentId(Number(saved));
      setBooted({ session, queue });
    })().catch((err) => console.error("start-up failed", err));
  }, []);

  if (!booted) return null;
  return (
    <Ready booted={booted} allotmentId={allotmentId} setAllotmentId={setAllotmentId}>
      {children}
    </Ready>
  );
}

function Ready({
  booted,
  allotmentId,
  setAllotmentId,
  children,
}: {
  booted: Booted;
  allotmentId: number | null;
  setAllotmentId: (id: number) => void;
  children: React.ReactNode;
}) {
  const { session, queue } = booted;
  const signedIn = useSyncExternalStore(
    (fn) => session.onChange(fn),
    () => session.signedIn,
  );
  const serverUrl = useSyncExternalStore(
    (fn) => session.onChange(fn),
    () => session.serverUrl,
  );
  const api = useMemo(() => createApi(session), [session, serverUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // Work through the queue on start-up, on a timer, and whenever the app comes back to the front.
  useEffect(() => {
    if (!signedIn) return;
    const run = () => void queue.run();
    run();
    const timer = setInterval(run, RUN_EVERY_MS);
    const sub = AppState.addEventListener("change", (s) => s === "active" && run());
    const stop = queue.subscribe(() => undefined);
    return () => {
      clearInterval(timer);
      sub.remove();
      stop();
    };
  }, [queue, signedIn]);

  useEffect(() => session.onExpired(() => queryClient.clear()), [session]);

  const value: AppContextValue = {
    session,
    queue,
    api,
    signedIn,
    allotmentId,
    chooseAllotment: (id) => {
      setAllotmentId(id);
      void secureStore.set(ALLOTMENT_KEY, String(id));
    },
  };
  return (
    <QueryClientProvider client={queryClient}>
      <AppContext.Provider value={value}>{children}</AppContext.Provider>
    </QueryClientProvider>
  );
}
