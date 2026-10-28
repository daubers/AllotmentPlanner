import { Directory, File, Paths } from "expo-file-system";

/** Move a fresh photo out of the camera's temporary folder (which the system may empty) into the
 *  app's own storage, where it waits for upload. Returns the new location. */
export async function keepPhoto(tempUri: string, clientId: string): Promise<string> {
  const dir = new Directory(Paths.document, "captures");
  dir.create({ idempotent: true, intermediates: true });
  const target = new File(dir, `${clientId}.jpg`);
  await new File(tempUri).move(target);
  return target.uri;
}
