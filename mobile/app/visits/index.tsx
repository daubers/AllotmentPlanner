import { useRouter } from "expo-router";
import React from "react";
import { useApp } from "../../src/state/AppProvider";
import { useCanEdit } from "../../src/tasks/hooks";
import { Banner, Button, Card, Empty, Loading, Row, Screen, Section, T } from "../../src/ui/kit";
import { useVisits } from "../../src/visits/hooks";

export default function Visits() {
  const router = useRouter();
  const { allotmentId } = useApp();
  const visits = useVisits();
  const canEdit = useCanEdit();
  const now = new Date();
  const upcoming = (visits.data ?? []).filter((v) => new Date(v.starts_at!) >= now);
  const past = (visits.data ?? []).filter((v) => new Date(v.starts_at!) < now);

  const when = (v: (typeof upcoming)[number]) =>
    new Date(v.starts_at!).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

  return (
    <Screen title="Visits" subtitle="Plan a trip to the plot, peg jobs to it, and add it to your calendar.">
      {allotmentId === null ? <Empty title="No allotment chosen" body="Choose one on the home screen." /> : null}
      {visits.isError ? <Banner tone="danger" text={(visits.error as Error).message} action="Try again" onAction={() => visits.refetch()} /> : null}
      {visits.isLoading ? <Loading /> : null}
      {canEdit ? <Button label="Plan a visit" onPress={() => router.push("/visits/new")} /> : <T kind="caption" muted>You can look at visits but not change them.</T>}
      {visits.data && upcoming.length === 0 && past.length === 0 ? (
        <Empty title="No visits planned" body="Plan one so you don't forget what to bring, and add it to your calendar." />
      ) : null}
      {upcoming.length > 0 ? (
        <Section title="Upcoming" right={<T kind="caption" muted>{upcoming.length}</T>}>
          <Card>
            {upcoming.map((v, i) => (
              <Row
                key={v.id}
                first={i === 0}
                title={v.title ?? "Visit"}
                subtitle={when(v)}
                onPress={() => router.push({ pathname: "/visits/[id]", params: { id: String(v.id) } })}
              />
            ))}
          </Card>
        </Section>
      ) : null}
      {past.length > 0 ? (
        <Section title="Past" right={<T kind="caption" muted>{past.length}</T>}>
          <Card>
            {past.map((v, i) => (
              <Row
                key={v.id}
                first={i === 0}
                dim
                title={v.title ?? "Visit"}
                subtitle={when(v)}
                onPress={() => router.push({ pathname: "/visits/[id]", params: { id: String(v.id) } })}
              />
            ))}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
