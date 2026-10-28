import { useQuery } from "@tanstack/react-query";
import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp, useQueueState } from "../src/app/AppProvider";
import type { Job } from "../src/queue/queue";
import { makeStyles, usePalette } from "../src/ui/theme";

export default function Home() {
  const { api, session, queue, allotmentId, chooseAllotment } = useApp();
  const palette = usePalette();
  const s = useMemo(() => makeStyles(palette), [palette]);
  const state = useQueueState();
  const router = useRouter();
  const [failed, setFailed] = useState<Job[]>([]);

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

  useEffect(() => {
    void queue.jobs().then((jobs) => setFailed(jobs.filter((j) => j.status === "failed")));
  }, [queue, state.pending, state.failed]);

  const waiting = state.pending;
  return (
    <SafeAreaView style={s.screen}>
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.title}>Allotment</Text>

        <View style={s.card}>
          <Text style={s.heading}>Your allotments</Text>
          {allotments.isLoading ? <ActivityIndicator /> : null}
          {allotments.isError ? (
            <>
              <Text style={s.error}>{allotments.error.message}</Text>
              <Pressable style={s.ghost} onPress={() => allotments.refetch()}>
                <Text style={s.ghostText}>Try again</Text>
              </Pressable>
            </>
          ) : null}
          {allotments.data?.map((a) => (
            <Pressable
              key={a.id}
              style={[s.row, { opacity: a.id === allotmentId ? 1 : 0.7 }]}
              onPress={() => a.id !== undefined && chooseAllotment(a.id)}
              accessibilityRole="radio"
              accessibilityState={{ selected: a.id === allotmentId }}
            >
              <Text style={s.text}>{a.id === allotmentId ? "● " : "○ "}{a.name}</Text>
              <Text style={s.muted}>{a.role}</Text>
            </Pressable>
          ))}
          {allotments.data?.length === 0 ? <Text style={s.muted}>No allotments yet. Create one in the web app.</Text> : null}
        </View>

        <Pressable
          style={[s.button, { opacity: allotmentId === null ? 0.5 : 1 }]}
          disabled={allotmentId === null}
          onPress={() => router.push("/capture")}
          accessibilityRole="button"
        >
          <Text style={s.buttonText}>Photograph the plot</Text>
        </Pressable>

        <View style={s.card}>
          <Text style={s.heading}>Waiting to send</Text>
          <Text style={s.text}>
            {waiting === 0 ? "Everything is sent." : `${waiting} waiting to upload`}
          </Text>
          {state.active ? (
            <Text style={s.muted}>
              Sending now… {Math.round(state.active.progress * 100)}%
            </Text>
          ) : null}
          {failed.map((job) => (
            <View key={job.id} style={{ gap: 6 }}>
              <Text style={s.error}>{job.error ?? "Failed"}</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable style={[s.ghost, { flex: 1 }]} onPress={() => queue.retry(job.id).then(() => queue.run())}>
                  <Text style={s.ghostText}>Retry</Text>
                </Pressable>
                <Pressable style={[s.ghost, { flex: 1 }]} onPress={() => queue.drop(job.id)}>
                  <Text style={s.ghostText}>Discard</Text>
                </Pressable>
              </View>
            </View>
          ))}
          {waiting > 0 ? (
            <Pressable style={s.ghost} onPress={() => queue.run()}>
              <Text style={s.ghostText}>Send now</Text>
            </Pressable>
          ) : null}
        </View>

        <View style={s.card}>
          <Text style={s.muted}>{session.serverUrl}</Text>
          <Pressable style={s.ghost} onPress={() => session.logout()}>
            <Text style={s.ghostText}>Sign out</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
