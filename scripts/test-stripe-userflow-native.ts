#!/usr/bin/env pnpm tsx
/**
 * Open Design Native Stripe User Flow Crawl & Figma Artifact Generator
 * ===================================================================
 * 100% Native Open Design TypeScript script using Node 24 fetch primitives.
 * Crawls https://stripe.com/in, extracts Information Architecture (IA), header links,
 * action buttons, footer navigation columns, compiles W3C design tokens, and packages
 * ready-to-use downloadable Figma import bundles.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportFigmaArtifacts, generateW3CTokens, generateFigmaImportBundle } from './export-figma-artifacts.js';

const TARGET_URL = 'https://stripe.com/in';
const OUTPUT_DIR = path.resolve('dist/stripe-in-artifacts');

interface VisualElement {
  text: string;
  tag: string;
  href?: string;
}

interface PageCapture {
  url: string;
  title: string;
  status: number;
  extracted_at: string;
  visual_hierarchy: {
    Header: {
      Buttons: VisualElement[];
      NavLinks: VisualElement[];
      Dropdowns: Record<string, VisualElement[]>;
    };
    Footer: {
      Columns: Record<string, VisualElement[]>;
    };
  };
}

export async function crawlStripeUserFlowNative(url: string = TARGET_URL, outDir: string = OUTPUT_DIR) {
  console.log(`🚀 Open Design Native Crawler starting for target URL: ${url}`);
  fs.mkdirSync(outDir, { recursive: true });

  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OpenDesign/2.4',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
  };

  try {
    console.log(`🌐 Requesting HTML structure from ${url}...`);
    const response = await fetch(url, { headers });
    const htmlText = await response.text();
    console.log(`  ✅ Received response (Status: ${response.status}, Bytes: ${htmlText.length})`);

    // Extract Title
    const titleMatch = htmlText.match(/<title[^>]*>([^<]+)<\/title>/i);
    const title = titleMatch ? titleMatch[1].trim() : 'Stripe India | Financial Infrastructure for the Internet';

    // Extract Links, Headings & Nav Items
    const linkMatches = Array.from(htmlText.matchAll(/<a\s+[^>]*href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gis));
    
    const headerButtons: VisualElement[] = [];
    const headerNavLinks: VisualElement[] = [];
    const dropdowns: Record<string, VisualElement[]> = {
      'Products & Solutions': [],
      'Developers & Docs': [],
      'Company & Resources': [],
    };
    const footerColumns: Record<string, VisualElement[]> = {
      'Products': [],
      'Solutions': [],
      'Developers': [],
      'Company': [],
    };

    for (const match of linkMatches) {
      const rawHref = match[1];
      const rawContent = match[2].replace(/<[^>]+>/g, '').trim();

      if (!rawContent || rawContent.length < 2 || rawContent.length > 60) continue;
      
      let fullUrl = rawHref;
      if (rawHref.startsWith('/')) {
        fullUrl = `https://stripe.com${rawHref}`;
      }

      const item: VisualElement = { text: rawContent, tag: 'a', href: fullUrl };

      // Categorize into visual hierarchy
      const lower = rawContent.toLowerCase();
      if (lower.includes('sign in') || lower.includes('contact sales') || lower.includes('get started') || lower.includes('try')) {
        headerButtons.push(item);
      } else if (lower.includes('payments') || lower.includes('billing') || lower.includes('connect') || lower.includes('issuing')) {
        dropdowns['Products & Solutions'].push(item);
      } else if (lower.includes('documentation') || lower.includes('api') || lower.includes('guides')) {
        dropdowns['Developers & Docs'].push(item);
      } else if (lower.includes('about') || lower.includes('jobs') || lower.includes('newsroom') || lower.includes('privacy')) {
        footerColumns['Company'].push(item);
      } else {
        headerNavLinks.push(item);
      }
    }

    const captureData: PageCapture = {
      url,
      title,
      status: response.status,
      extracted_at: new Date().toISOString(),
      visual_hierarchy: {
        Header: {
          Buttons: headerButtons.slice(0, 10),
          NavLinks: headerNavLinks.slice(0, 15),
          Dropdowns: dropdowns,
        },
        Footer: {
          Columns: footerColumns,
        },
      },
    };

    // Save Raw IA Graph
    const rawGraphPath = path.join(outDir, 'raw_ia_graph.json');
    fs.writeFileSync(rawGraphPath, JSON.stringify({ [url]: captureData }, null, 2), 'utf-8');
    console.log(`  ✅ Raw IA Graph generated: ${rawGraphPath}`);

    // Generate W3C Tokens & Figma Auto-Layout Import Bundle
    const tokens = generateW3CTokens();
    const importBundle = generateFigmaImportBundle(tokens);
    (importBundle as Record<string, unknown>).pages = [captureData];
    (importBundle as Record<string, unknown>).raw_graph = { [url]: captureData };

    const tokensPath = path.join(outDir, 'design_tokens.json');
    const bundlePath = path.join(outDir, 'figma_import_bundle.json');
    const odFigmaPath = path.join(outDir, 'stripe-in.od-figma.json');

    fs.writeFileSync(tokensPath, JSON.stringify(tokens, null, 2), 'utf-8');
    fs.writeFileSync(bundlePath, JSON.stringify(importBundle, null, 2), 'utf-8');
    fs.writeFileSync(odFigmaPath, JSON.stringify(importBundle, null, 2), 'utf-8');

    console.log('\n🎉 Native Stripe User Flow Crawl & Figma Artifact Generation Completed Successfully!');
    console.log(`   - Target: ${url}`);
    console.log(`   - Title: "${title}"`);
    console.log(`   - Extracted Header Actions: ${headerButtons.length}`);
    console.log(`   - Extracted Nav Links: ${headerNavLinks.length}`);
    console.log(`📂 Output Files at ${outDir}:`);
    console.log(`   • ${tokensPath}`);
    console.log(`   • ${bundlePath}`);
    console.log(`   • ${odFigmaPath}`);

  } catch (err) {
    console.error('❌ Error during native crawl:', err);
    throw err;
  }
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(process.argv[1]) === currentFile) {
  crawlStripeUserFlowNative();
}
