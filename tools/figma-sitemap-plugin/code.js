figma.showUI(__html__, { width: 440, height: 480 });

figma.ui.onmessage = async (msg) => {
  if (msg.type === 'GENERATE_SITEMAP') {
    try {
      await figma.loadFontAsync({ family: "Inter", style: "Regular" });
      await figma.loadFontAsync({ family: "Inter", style: "Medium" });
      await figma.loadFontAsync({ family: "Inter", style: "Bold" });

      const payload = msg.payload;
      const rootFrame = figma.createFrame();
      rootFrame.name = "Sitemap Architecture Map";
      rootFrame.fills = [{ type: 'SOLID', color: { r: 0.96, g: 0.97, b: 0.99 } }];
      rootFrame.paddingLeft = 60;
      rootFrame.paddingRight = 60;
      rootFrame.paddingTop = 60;
      rootFrame.paddingBottom = 60;

      // Extract hierarchy from JSON payload
      const columns = extractHierarchy(payload);
      
      let currentX = 60;
      const startY = 60;
      const columnGap = 60;

      for (const colKey of Object.keys(columns)) {
        const colData = columns[colKey];
        const colWidth = renderColumn(rootFrame, colKey, colData, currentX, startY);
        currentX += colWidth + columnGap;
      }

      rootFrame.resize(Math.max(1200, currentX + 60), 1200);
      figma.currentPage.appendChild(rootFrame);
      figma.viewport.scrollAndZoomIntoView([rootFrame]);
      figma.notify("Sitemap Tree generated successfully!");
    } catch (err) {
      figma.notify("Error generating sitemap: " + err.message);
    }
  }
};

function extractHierarchy(data) {
  const result = {};

  // Case A: raw_ia_graph.json
  if (typeof data === 'object' && !data.nodes) {
    for (const url in data) {
      const page = data[url];
      const ia = page.ia || {};
      const navItems = ia.navigation || [];
      const vh = page.visual_hierarchy || {};
      const drops = vh.Header ? vh.Header.Dropdowns : null;

      if (drops && Object.keys(drops).length > 0) {
        for (const dropKey in drops) {
          result[dropKey] = drops[dropKey];
        }
      } else if (navItems.length > 0) {
        const mainNav = [];
        for (const item of navItems) {
          if (item.name && item.name.length < 40) {
            mainNav.push(item.name);
          }
        }
        result["Navigation"] = { "Main Links": mainNav };
      }
    }
  } 
  // Case B: sitemap_figma.json
  else if (data.nodes) {
    result["Sitemap"] = {};
    for (const node of data.nodes) {
      const title = node.title || node.url || "Page";
      const children = (node.children || []).map(c => c.name || c.title || c);
      result["Sitemap"][title] = children;
    }
  }

  if (Object.keys(result).length === 0) {
    result["Sample Section"] = {
      "Overview": ["Dashboard", "Reports", "Analytics"],
      "Management": ["Users", "Settings", "Permissions"]
    };
  }

  return result;
}

function renderColumn(parentFrame, title, colData, startX, startY) {
  const colHeaderWidth = 200;
  const colHeaderHeight = 46;
  const itemWidth = 180;
  const itemHeight = 36;
  const itemGapY = 12;

  // 1. Top Header Card (Solid Blue)
  const headerCard = figma.createFrame();
  headerCard.name = "Header - " + title;
  headerCard.resize(colHeaderWidth, colHeaderHeight);
  headerCard.x = startX;
  headerCard.y = startY;
  headerCard.cornerRadius = 8;
  headerCard.fills = [{ type: 'SOLID', color: { r: 0.15, g: 0.39, b: 0.92 } }]; // #2563eb
  headerCard.strokes = [{ type: 'SOLID', color: { r: 0.23, g: 0.51, b: 0.96 } }];

  const headerText = figma.createText();
  headerText.fontName = { family: "Inter", style: "Bold" };
  headerText.characters = title;
  headerText.fontSize = 14;
  headerText.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 } }];
  headerText.x = 16;
  headerText.y = 13;
  headerCard.appendChild(headerText);
  parentFrame.appendChild(headerCard);

  let currentY = startY + colHeaderHeight + 24;
  let maxColWidth = colHeaderWidth;

  // Render Sub-groups & items
  if (typeof colData === 'object' && !Array.isArray(colData)) {
    for (const groupName in colData) {
      const items = colData[groupName];

      // Draw L-shaped connector line from header to subgroup card
      const itemCardX = startX + 24;
      drawLConnector(parentFrame, startX + 20, currentY - 12, itemCardX, currentY + itemHeight / 2);

      // Subgroup Card (Medium Blue)
      const groupCard = createCard(groupName, itemCardX, currentY, itemWidth, itemHeight, true);
      parentFrame.appendChild(groupCard);
      currentY += itemHeight + itemGapY;

      // Nested Items (Light Blue Stack)
      if (Array.isArray(items) && items.length > 0) {
        const nestedX = itemCardX + 24;
        const subGroupStartY = currentY;

        for (const item of items) {
          const itemTitle = typeof item === 'string' ? item : (item.text || item.name || "Item");
          const subCard = createCard(itemTitle, nestedX, currentY, itemWidth - 16, 32, false);
          parentFrame.appendChild(subCard);

          // Elbow connector for nested items
          drawLConnector(parentFrame, itemCardX + 16, currentY + 16, nestedX, currentY + 16);
          currentY += 32 + 8;
        }

        maxColWidth = Math.max(maxColWidth, 24 + 24 + itemWidth);
      }
    }
  } else if (Array.isArray(colData)) {
    for (const item of colData) {
      const itemTitle = typeof item === 'string' ? item : (item.text || item.name || "Item");
      const itemCardX = startX + 24;
      const card = createCard(itemTitle, itemCardX, currentY, itemWidth, itemHeight, false);
      parentFrame.appendChild(card);

      drawLConnector(parentFrame, startX + 20, currentY - 10, itemCardX, currentY + itemHeight / 2);
      currentY += itemHeight + itemGapY;
    }
  }

  return maxColWidth;
}

function createCard(title, x, y, width, height, isHighlight) {
  const card = figma.createFrame();
  card.name = "Node - " + title;
  card.resize(width, height);
  card.x = x;
  card.y = y;
  card.cornerRadius = 6;

  if (isHighlight) {
    card.fills = [{ type: 'SOLID', color: { r: 0.23, g: 0.51, b: 0.96 } }]; // Highlighted Blue
    card.strokes = [{ type: 'SOLID', color: { r: 0.15, g: 0.39, b: 0.92 } }];
  } else {
    card.fills = [{ type: 'SOLID', color: { r: 0.86, g: 0.92, b: 0.99 } }]; // Light Blue #dbeafe
    card.strokes = [{ type: 'SOLID', color: { r: 0.57, g: 0.77, b: 0.99 } }]; // #93c5fd
  }

  const text = figma.createText();
  text.fontName = { family: "Inter", style: isHighlight ? "Bold" : "Medium" };
  text.characters = title.substring(0, 24);
  text.fontSize = isHighlight ? 12 : 11;
  text.fills = [{ type: 'SOLID', color: isHighlight ? { r: 1, g: 1, b: 1 } : { r: 0.12, g: 0.16, b: 0.23 } }];
  text.x = 12;
  text.y = Math.floor((height - 14) / 2);
  card.appendChild(text);

  return card;
}

function drawLConnector(parentFrame, x1, y1, x2, y2) {
  const vector = figma.createVector();
  const midY = (y1 + y2) / 2;
  vector.vectorPaths = [{
    windingRule: "NONE",
    data: `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`
  }];
  vector.strokes = [{ type: 'SOLID', color: { r: 0.23, g: 0.51, b: 0.96 } }]; // #3b82f6
  vector.strokeWeight = 1.5;
  parentFrame.appendChild(vector);
}
