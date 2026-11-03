// Makes the release build type in the generated android/app/build.gradle sign with the keystore named
// by ANDROID_KEYSTORE_PATH / _PASSWORD / ANDROID_KEY_ALIAS (read from the environment by Gradle, so no
// secret is written to disk beyond the keystore itself).
const fs = require("fs");
const file = process.argv[2];
let g = fs.readFileSync(file, "utf8");

const block = `
        release {
            storeFile file(System.getenv("ANDROID_KEYSTORE_PATH"))
            storePassword System.getenv("ANDROID_KEYSTORE_PASSWORD")
            keyAlias System.getenv("ANDROID_KEY_ALIAS")
            keyPassword System.getenv("ANDROID_KEYSTORE_PASSWORD")
        }`;
const sc = g.match(/signingConfigs\s*\{/);
if (!sc) throw new Error("signingConfigs block not found in " + file);
g = g.slice(0, sc.index + sc[0].length) + block + g.slice(sc.index + sc[0].length);

const bt = g.search(/buildTypes\s*\{/);
const rel = bt < 0 ? -1 : g.slice(bt).search(/\brelease\s*\{/);
if (rel < 0) throw new Error("release build type not found in " + file);
const from = bt + rel;
const rest = g.slice(from);
const re = /signingConfig\s+signingConfigs\.debug/;
if (!re.test(rest)) throw new Error("release signingConfig line not found in " + file);
g = g.slice(0, from) + rest.replace(re, "signingConfig signingConfigs.release");
fs.writeFileSync(file, g);
