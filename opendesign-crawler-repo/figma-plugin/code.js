// code.js – Open Design IA Figma Plugin (v2 – Mega-Menu Aware)
//
// New JSON shape produced by the upgraded crawler:
//   {
//     "<url>": {
//       "visual_hierarchy": {
//         "Header": {
//           "Buttons": [{ text, href }],
//           "Dropdowns": {
//             "Products": {                    ← nav trigger label
//               "By stage":    [{ text, href }],   ← column heading
//               "By use case": [{ text, href }],
//               ...
//             },
//             "Solutions": { ... },
//             "Main Nav": { "Links": [...] }   ← flat fallback
//           }
//         },
//         "Footer": {
//           "Columns": { "Company": [...], "Products": [...] }
//         }
//       }
//     }
//   }

// ─── Design tokens ────────────────────────────────────────────
const CLR = {
  pageBg:      { r: 0.04, g: 0.04, b: 0.10 },
  headerBg:    { r: 0.06, g: 0.08, b: 0.20 },
  footerBg:    { r: 0.05, g: 0.14, b: 0.10 },
  dropdownBg:  { r: 0.09, g: 0.11, b: 0.26 },
  colCardBg:   { r: 0.12, g: 0.14, b: 0.30 },
  footColBg:   { r: 0.08, g: 0.18, b: 0.14 },
  stroke:      { r: 0.22, g: 0.28, b: 0.60 },
  footStroke:  { r: 0.12, g: 0.45, b: 0.35 },
  white:       { r: 1.00, g: 1.00, b: 1.00 },
  lightBlue:   { r: 0.75, g: 0.82, b: 1.00 },
  muted:       { r: 0.55, g: 0.60, b: 0.80 },
  mint:        { r: 0.55, g: 1.00, b: 0.78 },
  mutedMint:   { r: 0.45, g: 0.80, b: 0.65 },
  accent:      { r: 0.45, g: 0.55, b: 1.00 },
};

// ─── Paint helpers ────────────────────────────────────────────
const fill   = c => [{ type: "SOLID", color: c }];
const stroke = c => [{ type: "SOLID", color: c }];
const noFill = () => [];

// ─── Font loading ─────────────────────────────────────────────
async function loadFonts() {
  await figma.loadFontAsync({ family: "Roboto", style: "Regular" });
  await figma.loadFontAsync({ family: "Roboto", style: "Bold" });
}

// ─── Text node factory ────────────────────────────────────────
function txt(content, size, color, bold) {
  const t = figma.createText();
  t.fontName = { family: "Roboto", style: bold ? "Bold" : "Regular" };
  t.characters = (content || "").substring(0, 80) || "–";
  t.fontSize = size;
  t.fills = fill(color);
  return t;
}

// ─── Divider ─────────────────────────────────────────────────
function divider(width, color) {
  const d = figma.createFrame();
  d.resize(width, 1);
  d.fills = fill(color);
  d.name = "---";
  return d;
}

// ─── Auto-layout frame factory ────────────────────────────────
function frame(name, { mode = "VERTICAL", gap = 8, padH = 16, padV = 12,
                       bg, strokeColor, strokeW = 1, radius = 8, w } = {}) {
  const f = figma.createFrame();
  f.name = name;
  f.layoutMode = mode;
  f.primaryAxisSizingMode = "AUTO";
  f.counterAxisSizingMode = w ? "FIXED" : "AUTO";
  if (w) f.resize(w, 10);
  f.itemSpacing = gap;
  f.paddingTop = padV;
  f.paddingBottom = padV;
  f.paddingLeft = padH;
  f.paddingRight = padH;
  f.cornerRadius = radius;
  f.fills = bg ? fill(bg) : noFill();
  f.strokes = strokeColor ? stroke(strokeColor) : [];
  f.strokeWeight = strokeW;
  return f;
}

// ─── Column card (one sub-column inside a dropdown panel) ─────
function makeColCard(colName, items, isFooter) {
  const card = frame(colName, {
    bg: isFooter ? CLR.footColBg : CLR.colCardBg,
    strokeColor: isFooter ? CLR.footStroke : CLR.stroke,
    strokeW: 1,
    radius: 6,
    padH: 14,
    padV: 10,
    gap: 5,
    w: 240,
  });

  // Column heading
  card.appendChild(txt(colName, 11, isFooter ? CLR.mint : CLR.accent, true));
  card.appendChild(divider(212, isFooter ? CLR.footStroke : CLR.stroke));

  const safeItems = (items || []).slice(0, 15);
  for (const item of safeItems) {
    const label = typeof item === "string" ? item : (item.text || "");
    if (!label.trim()) continue;
    card.appendChild(txt("• " + label, 10, isFooter ? CLR.mutedMint : CLR.muted, false));
  }
  return card;
}

// ─── Dropdown panel (one nav trigger → multiple column cards) ─
function makeDropdownPanel(dropName, colMap, isFooter) {
  const panel = frame(dropName, {
    mode: "VERTICAL",
    bg: isFooter ? CLR.footerBg : CLR.dropdownBg,
    strokeColor: isFooter ? CLR.footStroke : CLR.stroke,
    strokeW: 1,
    radius: 10,
    padH: 16,
    padV: 14,
    gap: 12,
  });

  // Panel header
  panel.appendChild(txt(dropName, 13, isFooter ? CLR.mint : CLR.lightBlue, true));
  panel.appendChild(divider(0, isFooter ? CLR.footStroke : CLR.stroke));

  // Column cards in horizontal row
  const row = frame(`${dropName}__cols`, {
    mode: "HORIZONTAL",
    gap: 10,
    padH: 0,
    padV: 0,
    radius: 0,
  });

  // colMap can be:
  //   { "By stage": [{text, href}...], "By use case": [...] }  ← new nested shape
  //   [{ text, href }...]                                        ← old flat shape (fallback)
  if (Array.isArray(colMap)) {
    // Old flat list — wrap in a single "Links" column card
    row.appendChild(makeColCard("Links", colMap, isFooter));
  } else {
    const colNames = Object.keys(colMap);
    if (colNames.length === 0) {
      // Edge case: empty dropdown
      row.appendChild(txt("(no items)", 10, CLR.muted, false));
    } else {
      for (const colName of colNames) {
        row.appendChild(makeColCard(colName, colMap[colName], isFooter));
      }
    }
  }

  panel.appendChild(row);
  return panel;
}

// ─── Region section (Header / Footer wrapper) ─────────────────
function makeRegionSection(regionName, dropdowns, isFooter) {
  const section = frame(regionName, {
    mode: "VERTICAL",
    bg: isFooter ? CLR.footerBg : CLR.headerBg,
    strokeColor: isFooter ? CLR.footStroke : CLR.stroke,
    strokeW: 2,
    radius: 14,
    padH: 24,
    padV: 20,
    gap: 20,
  });

  // Region title
  section.appendChild(txt(regionName.toUpperCase(), 18, CLR.white, true));
  section.appendChild(divider(0, isFooter ? CLR.footStroke : CLR.stroke));

  // Horizontal scroll of dropdown panels
  const panelRow = frame(`${regionName}__panels`, {
    mode: "HORIZONTAL",
    gap: 16,
    padH: 0,
    padV: 0,
    radius: 0,
  });

  const entries = Object.entries(dropdowns);
  if (entries.length === 0) {
    panelRow.appendChild(txt("(no data extracted)", 11, CLR.muted, false));
  } else {
    for (const [dropName, colMap] of entries) {
      panelRow.appendChild(makeDropdownPanel(dropName, colMap, isFooter));
    }
  }

  section.appendChild(panelRow);
  return section;
}

// ─── Aggregate across all crawled pages ───────────────────────
/**
 * Combines data from all URLs.
 * Returns:
 *   {
 *     Header: { "Products": { "By stage": Set, ... }, ... },
 *     Footer: { "Company": Set, ... }
 *   }
 * (Sets are used for dedup, converted to arrays before use)
 */
function aggregateIA(data) {
  const agg = {
    Header: {},  // { dropdownName: { colName: Set<string> } }
    Footer: {},  // { colName: Set<string> }
  };

  for (const url of Object.keys(data)) {
    const page = data[url] || {};
    const vh = page.visual_hierarchy || {};

    // ── Header Dropdowns ──────────────────────────────────────
    const dropdowns = (vh.Header || {}).Dropdowns || {};
    for (const [dropName, colMap] of Object.entries(dropdowns)) {
      if (!agg.Header[dropName]) agg.Header[dropName] = {};

      if (Array.isArray(colMap)) {
        // Old flat shape – put everything under "Links"
        if (!agg.Header[dropName]["Links"]) agg.Header[dropName]["Links"] = new Set();
        for (const item of colMap) {
          const t = typeof item === "string" ? item : (item.text || "");
          if (t.trim()) agg.Header[dropName]["Links"].add(t.trim());
        }
      } else {
        // New nested shape: { colName: [items] }
        for (const [colName, items] of Object.entries(colMap)) {
          if (!agg.Header[dropName][colName]) agg.Header[dropName][colName] = new Set();
          for (const item of (items || [])) {
            const t = typeof item === "string" ? item : (item.text || "");
            if (t.trim()) agg.Header[dropName][colName].add(t.trim());
          }
        }
      }
    }

    // ── Footer Columns ────────────────────────────────────────
    const columns = (vh.Footer || {}).Columns || {};
    for (const [colName, items] of Object.entries(columns)) {
      if (!agg.Footer[colName]) agg.Footer[colName] = new Set();
      for (const item of (items || [])) {
        const t = typeof item === "string" ? item : (item.text || "");
        if (t.trim()) agg.Footer[colName].add(t.trim());
      }
    }
  }

  // Convert Sets → sorted Arrays
  const result = { Header: {}, Footer: {} };
  for (const [drop, cols] of Object.entries(agg.Header)) {
    result.Header[drop] = {};
    for (const [col, s] of Object.entries(cols)) {
      result.Header[drop][col] = [...s].sort();
    }
  }
  for (const [col, s] of Object.entries(agg.Footer)) {
    result.Footer[col] = [...s].sort();
  }
  return result;
}

// ─── Main ─────────────────────────────────────────────────────
figma.showUI(__html__, { width: 360, height: 280 });

figma.ui.onmessage = async (msg) => {
  if (msg.type !== "import-ia") return;

  await loadFonts();

  let parsed;
  try {
    parsed = JSON.parse(msg.json);
  } catch {
    figma.notify("❌ Invalid JSON – please provide valid JSON.");
    return;
  }

  // Handle bundle schema vs raw graph
  let rawGraph = parsed;
  let tokens = null;
  if (parsed && parsed.schema === "open-design-figma-bundle") {
    rawGraph = parsed.raw_graph || {};
    tokens = parsed.tokens || null;
  }

  const ia = aggregateIA(rawGraph);

  const headerDropCount = Object.keys(ia.Header).length;
  const footerColCount  = Object.keys(ia.Footer).length;

  if (headerDropCount === 0 && footerColCount === 0 && !tokens) {
    figma.notify("⚠️ No navigation data or tokens found.");
    return;
  }

  // Root canvas frame
  const root = frame("🗺 Open Design IA Map", {
    mode: "VERTICAL",
    bg: CLR.pageBg,
    padH: 48,
    padV: 48,
    gap: 36,
    radius: 0,
  });
  root.name = "🗺 Open Design IA Map";

  // Title
  root.appendChild(txt("Information Architecture & Design Tokens", 28, CLR.white, true));
  root.appendChild(divider(0, CLR.stroke));

  // Render Token Palette if tokens exist
  if (tokens && tokens.color && tokens.color.brand) {
    const tokenSec = frame("Design Tokens Palette", { mode: "HORIZONTAL", gap: 16, padH: 16, padV: 12, bg: CLR.dropdownBg, strokeColor: CLR.stroke });
    for (const [key, val] of Object.entries(tokens.color.brand)) {
      const colorBox = frame(key, { mode: "VERTICAL", gap: 4, padH: 12, padV: 8, bg: CLR.colCardBg, radius: 6 });
      colorBox.appendChild(txt(val.label || key, 12, CLR.white, true));
      colorBox.appendChild(txt(val.$value, 11, CLR.muted, false));
      tokenSec.appendChild(colorBox);
    }
    root.appendChild(tokenSec);
  }

  // Header section
  if (headerDropCount > 0) {
    root.appendChild(makeRegionSection("Header Navigation", ia.Header, false));
  }

  // Footer section — wrap colMap as { colName: [items] }
  if (footerColCount > 0) {
    const footerWrapped = {};
    for (const [colName, items] of Object.entries(ia.Footer)) {
      footerWrapped[colName] = { Links: items };
    }
    root.appendChild(makeRegionSection("Footer Links", footerWrapped, true));
  }

  figma.currentPage.appendChild(root);
  figma.viewport.scrollAndZoomIntoView([root]);
  figma.notify(`✅ Done! Import completed successfully.`);
  figma.closePlugin();
};
