import { useEffect } from "react";
import { SITE_NAME } from "./site";

/** Sets the browser tab title (and the description search results show) for a public page. */
export function usePageTitle(title: string | null, description?: string): void {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE_NAME}` : SITE_NAME;
    const meta = document.querySelector('meta[name="description"]');
    if (description && meta) meta.setAttribute("content", description);
  }, [title, description]);
}
