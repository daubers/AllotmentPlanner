import * as Clipboard from "expo-clipboard";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import { showDialog } from "../../src/ui/dialog";
import { useApp } from "../../src/state/AppProvider";
import { useCanEdit, useTasks } from "../../src/tasks/hooks";
import { Banner, Button, Card, Loading, Row, Screen, Section, T } from "../../src/ui/kit";
import { shareVisitIcs, useCalendarFeed, useVisit, useVisitActions } from "../../src/visits/hooks";
import { bringLabel } from "../../src/visits/model";

export default function VisitDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const visitId = Number(id);
  const { allotmentId, session } = useApp();
  const visit = useVisit(visitId);
  const tasks = useTasks();
  const feed = useCalendarFeed();
  const actions = useVisitActions();
  const canEdit = useCanEdit();
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [sharing, setSharing] = useState(false);

  const pegged = (tasks.data ?? []).filter((t) => visit.data?.task_ids?.includes(t.id!));

  async function share() {
    if (!visit.data || allotmentId === null) return;
    setError(null);
    setSharing(true);
    try {
      await shareVisitIcs(session, allotmentId, visit.data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSharing(false);
    }
  }

  async function copyFeed() {
    if (!feed.data?.feed_url) return;
    await Clipboard.setStringAsync(feed.data.feed_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function confirmDelete() {
    showDialog({
      title: "Delete this visit?",
      message: "The jobs pegged to it are not touched.",
      actions: [
        {
          label: "Delete",
          kind: "primary",
          onPress: () => void actions.remove.mutateAsync(visitId).then(() => router.back()),
        },
        { label: "Cancel", kind: "secondary" },
      ],
    });
  }

  if (visit.isLoading) return <Screen title="Visit"><Loading /></Screen>;
  if (!visit.data) return <Screen title="Visit"><Banner tone="danger" text="Couldn't find that visit." /></Screen>;

  const when = new Date(visit.data.starts_at!).toLocaleString(undefined, { dateStyle: "full", timeStyle: "short" });

  return (
    <Screen title={visit.data.title ?? "Visit"} subtitle={`${when} · ${visit.data.duration_minutes ?? 120} min`}>
      {visit.data.notes ? <T>{visit.data.notes}</T> : null}
      {error ? <Banner tone="danger" text={error} /> : null}

      <Section title="Jobs to bring" right={<T kind="caption" muted>{pegged.length}</T>}>
        {pegged.length > 0 ? (
          <Card>
            {pegged.map((t, i) => <Row key={t.id} first={i === 0} title={t.title ?? "Job"} />)}
          </Card>
        ) : (
          <T muted>No jobs pegged to this visit.</T>
        )}
      </Section>

      <Section title="Equipment to bring" right={<T kind="caption" muted>{visit.data.bring?.length ?? 0}</T>}>
        {(visit.data.bring?.length ?? 0) > 0 ? (
          <Card>
            {(visit.data.bring ?? []).map((b, i) => <Row key={b.id} first={i === 0} title={bringLabel(b)} />)}
          </Card>
        ) : (
          <T muted>Nothing to bring.</T>
        )}
      </Section>

      <Section title="Add to calendar">
        <Button label="Share as a calendar file" onPress={() => void share()} busy={sharing} kind="secondary" />
        {feed.data?.feed_url ? (
          <Button label={copied ? "Copied!" : "Copy subscribe link (all visits)"} onPress={() => void copyFeed()} kind="quiet" small />
        ) : null}
      </Section>

      {canEdit ? <Button label="Delete visit" kind="danger" onPress={confirmDelete} /> : null}
    </Screen>
  );
}
