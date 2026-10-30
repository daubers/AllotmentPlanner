import { useEffect, useState } from "react";
import { api } from "../api/client";

/** Can anyone create an account here? `null` until the server has said; "invite" means by invitation only. */
export function useRegistration(): "open" | "invite" | null {
  const [mode, setMode] = useState<"open" | "invite" | null>(null);
  useEffect(() => {
    let live = true;
    void Promise.resolve(api.GET("/api/v1/auth/config")).then((r) => {
      if (live) setMode(r?.data?.registration === "invite" ? "invite" : "open");
    });
    return () => {
      live = false;
    };
  }, []);
  return mode;
}
