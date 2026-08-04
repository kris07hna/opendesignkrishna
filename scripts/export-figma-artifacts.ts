#!/usr/bin/env pnpm tsx
/**
 * Open Design Native Figma Artifact Exporter & Token Compiler
 * ==========================================================
 * Native TypeScript exporter for Open Design repository.
 * Compiles design system tokens, craft guidelines, component primitives,
 * and Open Design Figma IR (.od-figma.json) into downloadable Figma artifacts.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

interface DesignTokenGroup {
  [key: string]: {
    $type: string;
    $value: string | number | Record<string, unknown>;
    label?: string;
  };
}

interface W3CDesignTokens {
  color: {
    brand: DesignTokenGroup;
    neutral: DesignTokenGroup;
  };
  spacing: DesignTokenGroup;
  typography: {
    heading1: { $type: string; $value: Record<string, string> };
    heading2: { $type: string; $value: Record<string, string> };
    body: { $type: string; $value: Record<string, string> };
  };
  metadata: {
    generator: string;
    repository: string;
    timestamp: string;
  };
}

export function generateW3CTokens(): W3CDesignTokens {
  return {
    color: {
      brand: {
        primary: { $type: 'color', $value: '#6366F1', label: 'Open Design Indigo Accent' },
        secondary: { $type: 'color', $value: '#10B981', label: 'Emerald Mint' },
        darkBg: { $type: 'color', $value: '#0F172A', label: 'Slate 900 Canvas' },
        surface: { $type: 'color', $value: '#1E293B', label: 'Slate 800 Card' },
        border: { $type: 'color', $value: '#334155', label: 'Slate 700 Stroke' },
        textBright: { $type: 'color', $value: '#F8FAFC', label: 'Bright Text' },
        textMuted: { $type: 'color', $value: '#94A3B8', label: 'Muted Text' },
      },
      neutral: {
        white: { $type: 'color', $value: '#FFFFFF', label: 'Pure White' },
        black: { $type: 'color', $value: '#000000', label: 'Pure Black' },
      },
    },
    spacing: {
      xs: { $type: 'dimension', $value: '4px' },
      sm: { $type: 'dimension', $value: '8px' },
      md: { $type: 'dimension', $value: '16px' },
      lg: { $type: 'dimension', $value: '24px' },
      xl: { $type: 'dimension', $value: '32px' },
      '2xl': { $type: 'dimension', $value: '48px' },
    },
    typography: {
      heading1: {
        $type: 'typography',
        $value: { fontFamily: 'Inter', fontSize: '32px', fontWeight: '700', lineHeight: '1.2' },
      },
      heading2: {
        $type: 'typography',
        $value: { fontFamily: 'Inter', fontSize: '24px', fontWeight: '600', lineHeight: '1.3' },
      },
      body: {
        $type: 'typography',
        $value: { fontFamily: 'Inter', fontSize: '14px', fontWeight: '400', lineHeight: '1.5' },
      },
    },
    metadata: {
      generator: 'Open Design Native Exporter v2.4',
      repository: 'open-design',
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateFigmaImportBundle(tokens: W3CDesignTokens) {
  return {
    version: '2.4',
    schema: 'open-design-figma-bundle',
    tokens,
    auto_layout: {
      canvas_mode: 'RESPONSIVE_FLOW_BOARDS',
      desktop_frame: { width: 1440, padding: 48, gap: 32 },
      mobile_frame: { width: 375, padding: 20, gap: 16 },
    },
    components: [
      { name: 'Button/Primary', type: 'COMPONENT', width: 140, height: 40, bg: '#6366F1', label: 'Primary Action' },
      { name: 'Button/Secondary', type: 'COMPONENT', width: 140, height: 40, bg: '#10B981', label: 'Secondary Action' },
      { name: 'Card/Surface', type: 'COMPONENT', width: 320, height: 200, bg: '#1E293B', label: 'Content Surface' },
    ],
  };
}

export function exportFigmaArtifacts(outputDir: string) {
  const targetDir = path.resolve(outputDir);
  fs.mkdirSync(targetDir, { recursive: true });

  const tokens = generateW3CTokens();
  const importBundle = generateFigmaImportBundle(tokens);

  const tokensPath = path.join(targetDir, 'design_tokens.json');
  const bundlePath = path.join(targetDir, 'figma_import_bundle.json');
  const odFigmaPath = path.join(targetDir, 'open-design-export.od-figma.json');

  fs.writeFileSync(tokensPath, JSON.stringify(tokens, null, 2), 'utf-8');
  fs.writeFileSync(bundlePath, JSON.stringify(importBundle, null, 2), 'utf-8');
  fs.writeFileSync(odFigmaPath, JSON.stringify(importBundle, null, 2), 'utf-8');

  console.log(`✅ Open Design Figma artifacts exported to: ${targetDir}`);
  console.log(`   - W3C Design Tokens: ${tokensPath}`);
  console.log(`   - Figma Import Bundle: ${bundlePath}`);
  console.log(`   - Open Design Figma Sidecar: ${odFigmaPath}`);
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(process.argv[1]) === currentFile) {
  const outDir = process.argv[2] || 'dist/figma-artifacts';
  exportFigmaArtifacts(outDir);
}
