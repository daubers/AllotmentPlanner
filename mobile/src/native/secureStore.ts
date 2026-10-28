import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import type { KeyValueStore } from "../auth/session";

/** On the web (used only to preview the app in a browser) there is no secure storage. */
const webStore: KeyValueStore = {
  get: async (key) => globalThis.localStorage?.getItem(key) ?? null,
  set: async (key, value) => void globalThis.localStorage?.setItem(key, value),
  remove: async (key) => void globalThis.localStorage?.removeItem(key),
};

export const secureStore: KeyValueStore =
  Platform.OS === "web"
    ? webStore
    : {
        get: (key) => SecureStore.getItemAsync(key),
        set: (key, value) => SecureStore.setItemAsync(key, value),
        remove: (key) => SecureStore.deleteItemAsync(key),
      };
