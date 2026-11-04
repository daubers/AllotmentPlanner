import { useRouter } from "expo-router";
import React from "react";
import { useQueueState } from "../state/AppProvider";
import { Banner } from "./kit";

/** What is waiting to be sent, live: nothing when the queue is empty, progress while sending, a warning when something was refused.
 *  Put it on every screen that takes or picks photos so nobody leaves thinking a photo went when it has not. */
export default function UploadBanner() {
  const state = useQueueState();
  const router = useRouter();
  if (state.failed > 0) {
    return <Banner tone="danger" text={`${state.failed} ${state.failed === 1 ? "item" : "items"} couldn't be sent`} action="Review" onAction={() => router.push("/uploads")} />;
  }
  if (state.pending > 0) {
    return (
      <Banner
        tone="warn"
        text={state.active ? `Sending… ${Math.round(state.active.progress * 100)}%  (${state.pending} waiting)` : `${state.pending} waiting to send`}
        action="Details"
        onAction={() => router.push("/uploads")}
      />
    );
  }
  return null;
}
