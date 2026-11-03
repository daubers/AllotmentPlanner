/** Photos sent this run, so one can be taken back: the server's id for each, by the id the app gave it. Memory only. */
const sent = new Map<string, number>();
const takeBack = new Set<string>();

export function recordSent(clientId: string, mediaId: number): void {
  sent.set(clientId, mediaId);
}
export const sentMediaId = (clientId: string): number | undefined => sent.get(clientId);
export function forget(clientId: string): void {
  sent.delete(clientId);
  takeBack.delete(clientId);
}
/** Remove it from the server as soon as the upload under way finishes. */
export const removeWhenSent = (clientId: string) => void takeBack.add(clientId);
export const isTakenBack = (clientId: string): boolean => takeBack.has(clientId);
