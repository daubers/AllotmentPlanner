import { editText, formatLength, parseLength } from "./units";

function near(a: number | null, b: number) {
  expect(a).not.toBeNull();
  expect(a as number).toBeCloseTo(b, 4);
}

test("plain numbers are read in the allotment's unit", () => {
  near(parseLength("3.2"), 3.2);
  near(parseLength("3,2"), 3.2);
  near(parseLength("320", "cm"), 3.2);
  near(parseLength("10", "ft_in"), 3.048);
});

test("a unit typed after the number wins over the allotment's", () => {
  near(parseLength("320cm"), 3.2);
  near(parseLength("3.2 m", "cm"), 3.2);
  near(parseLength("3200mm"), 3.2);
  near(parseLength("126in"), 3.2004);
  near(parseLength("10ft"), 3.048);
  near(parseLength("10 feet"), 3.048);
});

test("feet and inches in the usual spellings", () => {
  const expected = 10 * 0.3048 + 6 * 0.0254;
  for (const text of ["10ft 6in", "10' 6\"", "10'6\"", "10 ft 6", "10’6”", "10' 6"]) near(parseLength(text), expected);
  near(parseLength("0ft 6in"), 0.1524);
});

test("things that are not lengths are refused", () => {
  for (const text of ["", "  ", "abc", "3.2.1", "-4", "3 apples", "10ft six"]) expect(parseLength(text)).toBeNull();
});

test("lengths are shown in the chosen unit", () => {
  expect(formatLength(3.2, "m")).toBe("3.20 m");
  expect(formatLength(3.2, "cm")).toBe("320 cm");
  expect(formatLength(10 * 0.3048 + 6 * 0.0254, "ft_in")).toBe(`10' 6"`);
  expect(formatLength(0.3, "ft_in")).toBe(`1' 0"`); // 11.8 in rounds up to a whole foot
});

test("an entry box is filled in so it reads back the same", () => {
  for (const [metres, unit] of [[3.2, "m"], [3.2, "cm"], [3.2004, "ft_in"]] as const) {
    near(parseLength(editText(metres, unit), unit), metres);
  }
});
