import React, { useEffect, useState } from "react";
import { View } from "react-native";
import { useApp, useQueueState } from "../src/state/AppProvider";
import type { Job } from "../src/queue/queue";
import { Button, Card, Chip, Empty, Row, Screen, Section, T } from "../src/ui/kit";
import { space } from "../src/ui/theme";

function describe(job: Job): string {
  const p = job.payload as { name?: string; path?: string; method?: string };
  if (job.kind === "upload") return `Photo ${p.name ?? ""}`.trim();
  if (p.path?.includes("/measurements/")) return "A measurement";
  return "A change";
}

export default function Uploads() {
  const { queue } = useApp();
  const state = useQueueState();
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => {
    void queue.jobs().then(setJobs);
  }, [queue, state.pending, state.failed, state.active?.id]);

  const failed = jobs.filter((j) => j.status === "failed");
  const waiting = jobs.filter((j) => j.status === "pending");

  return (
    <Screen
      title="Sending"
      subtitle="Everything you do is saved on this phone first and sent when there is signal."
      footer={waiting.length || failed.length ? <Button label="Send now" onPress={() => void queue.run()} /> : undefined}
    >
      {jobs.length === 0 ? <Empty title="All sent" body="Nothing is waiting. New photos and measurements will appear here until they reach the server." /> : null}

      {failed.length ? (
        <Section title="Couldn't be sent">
          {failed.map((job) => (
            <Card key={job.id} tone="danger">
              <T kind="heading">{describe(job)}</T>
              <T>{job.error ?? "The server refused it."}</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <View style={{ flex: 1 }}>
                  <Button label="Try again" small onPress={() => queue.retry(job.id).then(() => queue.run())} />
                </View>
                <View style={{ flex: 1 }}>
                  <Button label="Discard" kind="secondary" small onPress={() => queue.drop(job.id)} />
                </View>
              </View>
            </Card>
          ))}
        </Section>
      ) : null}

      {waiting.length ? (
        <Section title={`Waiting (${waiting.length})`}>
          <Card>
            {waiting.map((job, i) => {
              const sending = state.active?.id === job.id;
              return (
                <Row
                  key={job.id}
                  first={i === 0}
                  title={describe(job)}
                  subtitle={sending ? "Sending now" : job.attempts ? `Retrying: ${job.error ?? "no connection"}` : "Waiting for signal"}
                  value={sending ? `${Math.round(state.active!.progress * 100)}%` : undefined}
                  valueTone="ok"
                />
              );
            })}
          </Card>
        </Section>
      ) : null}
    </Screen>
  );
}
