/** The API level this app needs. It matches the server's `API_LEVEL`; raise both when the app relies on
 * something an older server lacks. A server that reports no level predates the check and counts as 0. */
export const REQUIRED_API_LEVEL = 1;

export interface ServerInfo {
  serverVersion?: string;
  apiLevel?: number;
  minAppVersion?: string;
}

export type Compat = { kind: "update-app" | "update-server"; message: string };

/** Compare dotted version numbers ("1.10.0" > "1.9.2"). Anything after a "-" or "+" is ignored. */
export function compareVersions(a: string, b: string): number {
  const parts = (v: string) => v.split(/[-+]/)[0].split(".").map((n) => parseInt(n, 10) || 0);
  const [x, y] = [parts(a), parts(b)];
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] ?? 0) - (y[i] ?? 0);
    if (d !== 0) return d < 0 ? -1 : 1;
  }
  return 0;
}

/** Whether this app and the server can work together; null when they can, or when the server can't be read. */
export function checkCompat(info: ServerInfo | null, appVersion: string): Compat | null {
  if (!info) return null;
  if (info.minAppVersion && compareVersions(appVersion, info.minAppVersion) < 0) {
    return { kind: "update-app", message: `This server needs app version ${info.minAppVersion} or newer (you have ${appVersion}). Update the app.` };
  }
  if ((info.apiLevel ?? 0) < REQUIRED_API_LEVEL) {
    return { kind: "update-server", message: "This app is newer than your server. Update the server, or use an older version of the app." };
  }
  return null;
}
