import { useEffect, useState } from "react";

/** `value`, but only once it has stopped changing for `ms` (so typing does not fire a request per key). */
export function useDebounced<T>(value: T, ms = 400): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}
