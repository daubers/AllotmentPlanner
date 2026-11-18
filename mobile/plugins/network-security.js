/**
 * Android network security config.
 *
 * Android can only allow plain HTTP per host name, never per address range, so it cannot say
 * "private networks only". The store build therefore allows cleartext just for `localhost`, the
 * emulator's host (10.0.2.2) and `*.local` names, and needs HTTPS everywhere else. A build made
 * with ALLOW_CLEARTEXT=1 (the sideloaded APK from CI, EAS development and preview) allows plain
 * HTTP anywhere, so a self-hosted server at http://192.168.x.x:8000 keeps working.
 */
const { withAndroidManifest, withDangerousMod } = require("expo/config-plugins");
const fs = require("fs");
const path = require("path");

function networkSecurityXml(allowAll) {
  if (allowAll) {
    return `<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="true" />
</network-security-config>
`;
  }
  return `<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="false" />
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="false">localhost</domain>
    <domain includeSubdomains="false">10.0.2.2</domain>
    <domain includeSubdomains="true">local</domain>
  </domain-config>
</network-security-config>
`;
}

const withNetworkSecurity = (config, props = {}) => {
  const allowAll = props.allowAll ?? process.env.ALLOW_CLEARTEXT === "1";

  config = withDangerousMod(config, [
    "android",
    (cfg) => {
      const dir = path.join(cfg.modRequest.platformProjectRoot, "app/src/main/res/xml");
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "network_security_config.xml"), networkSecurityXml(allowAll));
      return cfg;
    },
  ]);

  return withAndroidManifest(config, (cfg) => {
    const app = cfg.modResults.manifest.application[0];
    app.$["android:networkSecurityConfig"] = "@xml/network_security_config";
    delete app.$["android:usesCleartextTraffic"]; // the config above decides, on every Android we support
    return cfg;
  });
};

module.exports = withNetworkSecurity;
module.exports.networkSecurityXml = networkSecurityXml;
