const { networkSecurityXml } = require("./network-security");

test("the store build allows plain HTTP only to localhost, the emulator host and .local names", () => {
  const xml = networkSecurityXml(false);
  expect(xml).toContain('<base-config cleartextTrafficPermitted="false" />');
  expect(xml).toContain(">localhost<");
  expect(xml).toContain(">10.0.2.2<");
  expect(xml).toContain('includeSubdomains="true">local<');
  expect(xml).not.toContain("192.168");
});

test("a sideloaded build allows plain HTTP anywhere, so a LAN server keeps working", () => {
  const xml = networkSecurityXml(true);
  expect(xml).toContain('<base-config cleartextTrafficPermitted="true" />');
  expect(xml).not.toContain("domain-config");
});
