import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Pressable, View } from "react-native";
import { useFound } from "../src/found/hooks";
import JobSwitch from "../src/tasks/JobSwitch";
import PlotMap from "../src/plot/PlotMap";
import { jobsFor, pinsFor, type Selection } from "../src/plot/pins";
import { dueLabel } from "../src/tasks/model";
import { usePlotShapes } from "../src/plot/hooks";
import { useChecklist } from "../src/measure/hooks";
import { useApp, useQueueState } from "../src/state/AppProvider";
import { useDoneFlow, useTasks } from "../src/tasks/hooks";
import { localDate } from "../src/tasks/model";
import { Banner, Button, Card, Chip, Loading, ProgressBar, Row, Screen, Section, T } from "../src/ui/kit";
import { radius, space, usePalette } from "../src/ui/theme";

function Tile({
  title,
  body,
  onPress,
  primary,
  disabled,
  footer,
}: {
  title: string;
  body: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
  footer?: React.ReactNode;
}) {
  const p = usePalette();
  const fg = primary ? p.onAccent : p.text;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityHint={body}
      style={({ pressed }) => ({
        borderRadius: radius.lg,
        padding: space.lg,
        gap: space.sm,
        backgroundColor: primary ? p.accent : p.surface,
        borderWidth: 1,
        borderColor: primary ? p.accent : p.border,
        opacity: disabled ? 0.5 : pressed ? 0.9 : 1,
        minHeight: 96,
        justifyContent: "center",
      })}
    >
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <T kind="heading" style={{ color: fg, fontSize: 20 }}>
          {title}
        </T>
        <T kind="heading" style={{ color: fg }}>
          ›
        </T>
      </View>
      <T kind="body" style={{ color: fg, opacity: primary ? 0.92 : 1 }} muted={!primary}>
        {body}
      </T>
      {footer}
    </Pressable>
  );
}

/** A job in the map's card: tap the text to open it, flick the switch to mark it done. */
function JobLine({
  title,
  subtitle,
  late,
  done,
  first,
  canTick,
  onOpen,
  onTick,
}: {
  title: string;
  subtitle: string;
  late: boolean;
  done: boolean;
  first: boolean;
  canTick: boolean;
  onOpen: () => void;
  onTick: (done: boolean) => void;
}) {
  const p = usePalette();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingVertical: space.sm, borderTopWidth: first ? 0 : 1, borderTopColor: p.border }}>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={`Open job: ${title}`} style={{ flex: 1, gap: 2 }}>
        <T kind="body" style={{ fontWeight: "500", textDecorationLine: done ? "line-through" : "none" }} muted={done}>
          {title}
        </T>
        {subtitle ? (
          <T kind="caption" muted={!late} tone={late ? "danger" : undefined}>
            {subtitle}
          </T>
        ) : null}
      </Pressable>
      <JobSwitch title={title} done={done} disabled={!canTick} onChange={onTick} />
    </View>
  );
}

/** What to call the selected thing: its name, else its kind ("Bed", "Shed"), else where a job was pinned. */
function selectionName(sel: Selection, shapes: { id: number; kind: string; name: string }[]): string {
  if (sel.kind === "spot") return "Pinned on the map";
  const s = shapes.find((x) => x.id === sel.id);
  return s?.name || (s ? s.kind.charAt(0).toUpperCase() + s.kind.slice(1) : "This spot");
}

export default function Home() {
  const { api, session, queue, allotmentId, chooseAllotment } = useApp();
  const router = useRouter();
  const state = useQueueState();
  const checklist = useChecklist();
  const found = useFound();
  const tasks = useTasks();
  const finish = useDoneFlow();
  const plot = usePlotShapes();
  const today = localDate();
  const jobs = (tasks.data ?? []).filter((t) => t.status !== "done" && (!t.due_date || t.due_date <= today));
  const late = jobs.filter((t) => t.due_date && t.due_date < today).length;
  const [switching, setSwitching] = useState(false);
  const [selected, setSelected] = useState<Selection | null>(null);

  const allotments = useQuery({
    queryKey: ["allotments", session.serverUrl],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments");
      if (error || !data) throw new Error("Couldn't load your allotments");
      return data;
    },
  });

  // Pick the first allotment if none is chosen (or the saved one has gone).
  useEffect(() => {
    const list = allotments.data;
    const first = list?.[0]?.id;
    if (first !== undefined && !list?.some((a) => a.id === allotmentId)) chooseAllotment(first);
  }, [allotments.data, allotmentId, chooseAllotment]);

  const current = allotments.data?.find((a) => a.id === allotmentId);
  const many = (allotments.data?.length ?? 0) > 1;
  const canEdit = current ? current.role !== "viewer" : false;
  const c = checklist.data;

  const banner =
    state.failed > 0 ? (
      <Banner tone="danger" text={`${state.failed} ${state.failed === 1 ? "item" : "items"} couldn't be sent`} action="Review" onAction={() => router.push("/uploads")} />
    ) : state.pending > 0 ? (
      <Banner
        tone="warn"
        text={state.active ? `Sending… ${Math.round(state.active.progress * 100)}%  (${state.pending} waiting)` : `${state.pending} waiting to send`}
        action="Details"
        onAction={() => router.push("/uploads")}
      />
    ) : null;

  return (
    <Screen back={false}>
      <View style={{ gap: space.xs }}>
        <T kind="eyebrow" muted>
          YOUR PLOT
        </T>
        {allotments.isLoading ? (
          <T kind="title">Allotment</T>
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.md }}>
            <T kind="title" style={{ flex: 1 }} accessibilityRole="header">
              {current?.name ?? "Allotment"}
            </T>
            {many ? <Button label={switching ? "Close" : "Switch"} kind="secondary" small onPress={() => setSwitching(!switching)} /> : null}
          </View>
        )}
      </View>

      {switching && allotments.data ? (
        <Card>
          {allotments.data.map((a, i) => (
            <Row
              key={a.id}
              first={i === 0}
              title={a.name ?? ""}
              subtitle={a.role}
              value={a.id === allotmentId ? "Current" : undefined}
              valueTone="ok"
              onPress={() => {
                if (a.id !== undefined) chooseAllotment(a.id);
                setSwitching(false);
              }}
            />
          ))}
        </Card>
      ) : null}

      {banner}
      {allotments.isLoading ? <Loading label="Loading your plot…" /> : null}
      {allotments.isError ? <Banner tone="danger" text={allotments.error.message} action="Try again" onAction={() => allotments.refetch()} /> : null}
      {allotments.data?.length === 0 ? (
        <Card>
          <T kind="heading">No allotments yet</T>
          <T muted>Create one in the web app, then it will appear here.</T>
        </Card>
      ) : null}

      {current && plot.data && plot.data.length > 0 ? (
        <View style={{ gap: space.sm }}>
          <PlotMap shapes={plot.data} pins={pinsFor(plot.data, tasks.data, today)} selected={selected} onSelect={setSelected} />
          <T kind="caption" muted>
            {selected ? "Tap the ground to clear." : "Tap a bed or a numbered pin to see its jobs. Pins show jobs due today or late; red means late."}
          </T>
          {selected ? (
            <Card>
              <T kind="heading">{selectionName(selected, plot.data)}</T>
              {(() => {
                const list = jobsFor(selected, tasks.data);
                return list.length === 0 ? (
                  <T muted>No open jobs here.</T>
                ) : (
                  list.map((t, i) => (
                    <JobLine
                      key={t.id}
                      first={i === 0}
                      title={t.title ?? ""}
                      subtitle={[dueLabel(t.due_date), t.priority === "high" ? "High priority" : ""].filter(Boolean).join(" · ")}
                      late={!!t.due_date && t.due_date < today}
                      done={t.status === "done"}
                      canTick={canEdit && (t.id ?? 0) > 0}
                      onOpen={() => router.push({ pathname: "/tasks/[id]", params: { id: String(t.id) } })}
                      onTick={(done) => void finish(t.id!, t.title ?? "this job", done)}
                    />
                  ))
                );
              })()}
            </Card>
          ) : null}
        </View>
      ) : null}
      {current && plot.data && plot.data.length === 0 ? (
        <Card>
          <T kind="heading">Your map will appear here</T>
          <T muted>
            Nothing has been drawn for this plot yet. Open the web app, go to Map and draw your beds, paths and shed, or use "Photograph the plot" below to build a map from
            photos and trace over it on the web. Whatever you draw shows up here.
          </T>
        </Card>
      ) : null}

      {current ? (
        <Section title="What would you like to do?">
          <Tile
            primary
            title="Photograph the plot"
            body="Walk round the edge. The app records where each photo was taken so a map can be built."
            disabled={!canEdit}
            onPress={() => router.push("/capture")}
          />
          <Tile
            title="Measure the plot"
            body={c && c.items.length ? "Take distances with a tape to correct the map to real sizes." : "Take distances with a tape. First make the checklist from your drawn shapes."}
            disabled={!canEdit}
            onPress={() => router.push("/measure")}
            footer={
              c && c.total > 0 ? (
                <View style={{ gap: space.xs }}>
                  <ProgressBar value={c.measured} total={c.total} />
                  <T kind="caption" muted>
                    {c.measured} of {c.total} measured
                  </T>
                </View>
              ) : undefined
            }
          />
          {canEdit && (found.data?.length ?? 0) > 0 ? (
            <Tile
              title="Review what was found"
              body={`${found.data!.length} ${found.data!.length === 1 ? "thing" : "things"} spotted in your photos. Check each against the photo and add it to the map.`}
              onPress={() => router.push("/found")}
            />
          ) : null}
          {!canEdit ? <T kind="caption" muted>You can look at this allotment but not change it.</T> : null}
        </Section>
      ) : null}

      {current ? (
        <Section title="Jobs">
          <Tile
            title="Jobs"
            body={jobs.length > 0 ? `${jobs.length} to do${late > 0 ? `, ${late} late` : ""}. Tick them off as you go; works without signal.` : "Tick jobs off as you go, or add one while you are on the plot. Works without signal."}
            onPress={() => router.push("/tasks")}
          />
        </Section>
      ) : null}

      {current ? (
        <Section title="Seeds and beds">
          <Tile title="Seeds" body="Your packets: what to sow this month, and scan a new one by photographing its back." onPress={() => router.push("/seeds")} />
          <Tile title="Seed trays" body="See what is sown where, and mark what has come up. Works without signal." onPress={() => router.push("/trays")} />
          <Tile title="Beds" body="What is growing in each bed, and how it is getting on." onPress={() => router.push("/beds")} />
        </Section>
      ) : null}

      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.md, marginTop: space.md }}>
        <View style={{ flex: 1 }}>
          <T kind="caption" muted numberOfLines={1}>
            {session.serverUrl}
          </T>
        </View>
        <Button label="Sign out" kind="quiet" small onPress={() => session.logout()} />
      </View>
    </Screen>
  );
}
