// Pure generators: design/tokens.json -> CSS variables + typed constants. No I/O here.
export const PREFIX = "--gc";

const kebab = (s) => String(s).replace(/_/g, "-");

function flat(prefix, obj, out = []) {
  for (const [k, v] of Object.entries(obj)) {
    if (v !== null && typeof v === "object") flat(`${prefix}-${kebab(k)}`, v, out);
    else out.push([`${prefix}-${kebab(k)}`, v]);
  }
  return out;
}

const px = (n) => `${n}px`;

function themeVars(theme) {
  const { series, band_opacity, ...colors } = theme;
  const out = flat(`${PREFIX}-color`, colors);
  out.push(...flat(`${PREFIX}-series`, series));
  out.push([`${PREFIX}-band-opacity`, band_opacity]);
  return out;
}

/** Returns [name, value] pairs for theme-independent tokens. */
export function baseVars(t) {
  const v = [];
  for (const [k, val] of Object.entries(t.font)) v.push([`${PREFIX}-font-${k}`, val]);
  for (const [k, val] of Object.entries(t.type_scale_px)) v.push([`${PREFIX}-text-${k}`, px(val)]);
  for (const [k, val] of Object.entries(t.line_height)) v.push([`${PREFIX}-leading-${k}`, val]);
  for (const [k, val] of Object.entries(t.weight)) v.push([`${PREFIX}-weight-${k}`, val]);
  for (const [k, val] of Object.entries(t.space_px)) v.push([`${PREFIX}-space-${k}`, px(val)]);
  for (const [k, val] of Object.entries(t.radius_px)) v.push([`${PREFIX}-radius-${k}`, px(val)]);
  for (const [k, val] of Object.entries(t.elevation)) v.push([`${PREFIX}-elevation-${k}`, val]);
  for (const [k, val] of Object.entries(t.layout)) v.push([`${PREFIX}-layout-${kebab(k.replace(/_px$/, ""))}`, px(val)]);
  for (const [k, val] of Object.entries(t.motion.duration_ms)) v.push([`${PREFIX}-duration-${k}`, `${val}ms`]);
  for (const [k, val] of Object.entries(t.motion.easing)) v.push([`${PREFIX}-easing-${k}`, val]);
  return v;
}

export function themeVarMap(t, name) {
  return Object.fromEntries(themeVars(t.themes[name]));
}

export function baseVarMap(t) {
  return Object.fromEntries(baseVars(t));
}

const block = (sel, pairs, ind = "") =>
  `${ind}${sel} {\n${pairs.map(([k, v]) => `${ind}  ${k}: ${v};`).join("\n")}\n${ind}}\n`;

export function buildCss(t) {
  const light = themeVars(t.themes.light);
  const dark = themeVars(t.themes.dark);
  const reduced = [
    ...Object.keys(t.motion.duration_ms)
      .filter((k) => k !== "instant")
      .map((k) => [`${PREFIX}-duration-${k}`, k === "fast" ? t.motion.duration_ms.fast + "ms" : "0ms"]),
  ];
  return [
    "/* GENERATED from design/tokens.json by `npm run gen`. Do not edit. */\n",
    block(":root", [...baseVars(t), ...light, ["color-scheme", "light"]]),
    "@media (prefers-color-scheme: dark) {\n" +
      block(':root:not([data-theme="light"])', [...dark, ["color-scheme", "dark"]], "  ") +
      "}\n",
    block(':root[data-theme="dark"]', [...dark, ["color-scheme", "dark"]]),
    "@media (prefers-reduced-motion: reduce) {\n" + block(":root", reduced, "  ") + "}\n",
  ].join("\n");
}

export function buildTokensModule(t) {
  return (
    "// GENERATED from design/tokens.json by `npm run gen`. Do not edit.\n" +
    `export const tokens = ${JSON.stringify(t, null, 2)} as const;\n`
  );
}
