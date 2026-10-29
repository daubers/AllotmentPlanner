import { useRouter } from "expo-router";
import React from "react";
import { summarise } from "../../src/trays/model";
import { useTrays } from "../../src/trays/hooks";
import { Banner, Card, Empty, Loading, Row, Screen } from "../../src/ui/kit";

export default function Trays() {
  const router = useRouter();
  const trays = useTrays();
  const list = (trays.data ?? []).filter((t) => t.status !== "finished");
  return (
    <Screen title="Seed trays" subtitle="What is sown where. Open a tray to mark what has come up.">
      {trays.isError ? <Banner tone="danger" text={(trays.error as Error).message} action="Try again" onAction={() => trays.refetch()} /> : null}
      {trays.isLoading ? <Loading /> : null}
      {trays.data && list.length === 0 ? <Empty title="No trays yet" body="Add a tray in the web app, then sow into it here or there." /> : null}
      {list.length > 0 ? (
        <Card>
          {list.map((t, i) => (
            <Row
              key={t.id}
              first={i === 0}
              title={t.name ?? "Tray"}
              subtitle={`${t.rows} × ${t.cols}${t.location ? ` · ${t.location}` : ""} · ${summarise(t.counts) || "nothing sown yet"}`}
              value={t.status === "planted_out" ? "Planted out" : undefined}
              onPress={() => router.push(`/trays/${t.id}`)}
            />
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
