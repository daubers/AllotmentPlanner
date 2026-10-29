import { useRouter } from "expo-router";
import React from "react";
import { areaLabel, GROWING } from "../../src/beds/geometry";
import { useBeds, usePlantings } from "../../src/beds/hooks";
import { Banner, Card, Empty, Loading, Row, Screen } from "../../src/ui/kit";

export default function Beds() {
  const router = useRouter();
  const beds = useBeds();
  const plantings = usePlantings();
  const growing = new Map<number, number>();
  for (const pl of plantings.data ?? []) if (GROWING.includes(pl.status ?? "")) growing.set(pl.feature_id!, (growing.get(pl.feature_id!) ?? 0) + 1);
  return (
    <Screen title="Beds" subtitle="What is growing where.">
      {beds.isError ? <Banner tone="danger" text={(beds.error as Error).message} action="Try again" onAction={() => beds.refetch()} /> : null}
      {beds.isLoading ? <Loading /> : null}
      {beds.data && beds.data.length === 0 ? <Empty title="No beds yet" body="Draw a bed as an area on the map in the web app (kind: bed)." /> : null}
      {beds.data && beds.data.length > 0 ? (
        <Card>
          {beds.data.map((b, i) => (
            <Row key={b.id} first={i === 0} title={b.name} subtitle={growing.get(b.id) ? `${growing.get(b.id)} growing` : "Empty"} onPress={() => router.push(`/beds/${b.id}`)} />
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
