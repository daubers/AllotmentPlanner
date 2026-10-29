import { useRouter } from "expo-router";
import React, { useState } from "react";
import { currentMonth, filterPackets, monthsLabel, packetTitle, STOCK_LABEL } from "../../src/seeds/model";
import { usePackets } from "../../src/seeds/hooks";
import { useApp } from "../../src/state/AppProvider";
import { Banner, Button, Card, Empty, Field, Loading, Row, Screen, Section, Segmented } from "../../src/ui/kit";

export default function Seeds() {
  const router = useRouter();
  const { allotmentId } = useApp();
  const packets = usePackets("active");
  const drafts = usePackets("draft");
  const [q, setQ] = useState("");
  const [when, setWhen] = useState<"all" | "now">("all");
  const list = filterPackets(packets.data ?? [], { q, month: when === "now" ? currentMonth() : null });

  return (
    <Screen
      title="Seeds"
      subtitle="Your packets: what to sow now, and how."
      footer={<Button label="Scan a packet" onPress={() => router.push("/photo?mode=scan")} disabled={allotmentId === null} />}
    >
      {packets.isError ? <Banner tone="danger" text={(packets.error as Error).message} action="Try again" onAction={() => packets.refetch()} /> : null}
      {drafts.data?.length ? (
        <Section title={`To review (${drafts.data.length})`}>
          <Card>
            {drafts.data.map((p, i) => (
              <Row key={p.id} first={i === 0} title={packetTitle(p)} subtitle={p.supplier || "Read from a photo"} value="Draft" valueTone="warn" onPress={() => router.push(`/seeds/${p.id}`)} />
            ))}
          </Card>
        </Section>
      ) : null}
      <Field label="Search" value={q} onChangeText={setQ} placeholder="Name, variety or supplier" autoCapitalize="none" />
      <Segmented value={when} onChange={setWhen} options={[{ value: "all", label: "All" }, { value: "now", label: "Sow this month" }]} />
      {packets.isLoading ? <Loading /> : null}
      {packets.data && list.length === 0 ? (
        <Empty title={q || when === "now" ? "Nothing matches" : "No packets yet"} body={q || when === "now" ? "Try a different search, or all months." : "Scan the back of a packet to add your first."} />
      ) : null}
      {list.length > 0 ? (
        <Card>
          {list.map((p, i) => (
            <Row
              key={p.id}
              first={i === 0}
              title={packetTitle(p)}
              subtitle={[p.supplier, monthsLabel([...(p.calendar?.sow_indoors ?? []), ...(p.calendar?.sow_outdoors ?? [])].sort((a, b) => a - b)) && `Sow ${monthsLabel([...(p.calendar?.sow_indoors ?? []), ...(p.calendar?.sow_outdoors ?? [])].sort((a, b) => a - b))}`].filter(Boolean).join(" · ")}
              value={p.stock && p.stock !== "full" ? STOCK_LABEL[p.stock] : undefined}
              valueTone={p.stock === "low" || p.stock === "empty" ? "danger" : "neutral"}
              onPress={() => router.push(`/seeds/${p.id}`)}
            />
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
