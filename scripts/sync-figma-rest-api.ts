#!/usr/bin/env pnpm tsx
/**
 * Open Design Figma REST API Direct Sync
 * =====================================
 * Native TypeScript helper that syncs Open Design tokens and workflow status comments
 * directly into target Figma files via Figma REST API endpoints.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as https from 'node:https';
import { fileURLToPath } from 'node:url';

const FIGMA_API_BASE = 'api.figma.com';

export async function syncToFigmaApi(fileKey?: string, token?: string, bundlePath?: string) {
  const figmaToken = token || process.env.FIGMA_ACCESS_TOKEN;
  const targetKey = fileKey || process.env.FIGMA_FILE_KEY;

  if (!figmaToken || !targetKey) {
    console.log('⚠️ FIGMA_ACCESS_TOKEN or FIGMA_FILE_KEY missing. Skipping direct Figma REST API push.');
    return false;
  }

  console.log(`🔄 Connecting to Figma REST API for File Key: ${targetKey}...`);

  const bundleFile = path.resolve(bundlePath || 'dist/figma-artifacts/figma_import_bundle.json');
  let pageCount = 1;
  if (fs.existsSync(bundleFile)) {
    try {
      const bundle = JSON.parse(fs.readFileSync(bundleFile, 'utf-8'));
      pageCount = bundle.pages?.length || 1;
    } catch {
      // fallback
    }
  }

  const postData = JSON.stringify({
    message: `🚀 [Open Design GitHub Action Pipeline] Export completed successfully!\n- Design Tokens & Auto-Layout frames ready.\n- Page/Component count: ${pageCount}\n- Importable via Open Design Figma Plugin.`,
  });

  const options: https.RequestOptions = {
    hostname: FIGMA_API_BASE,
    port: 443,
    path: `/v1/files/${targetKey}/comments`,
    method: 'POST',
    headers: {
      'X-Figma-Token': figmaToken,
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData),
    },
  };

  return new Promise((resolve) => {
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          console.log('✅ Successfully posted update comment on Figma canvas!');
          resolve(true);
        } else {
          console.log(`⚠️ Figma API returned status ${res.statusCode}: ${body}`);
          resolve(false);
        }
      });
    });

    req.on('error', (e) => {
      console.log(`⚠️ Error posting comment to Figma API: ${e.message}`);
      resolve(false);
    });

    req.write(postData);
    req.end();
  });
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(process.argv[1]) === currentFile) {
  syncToFigmaApi(process.argv[2], process.argv[3], process.argv[4]);
}
