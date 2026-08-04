#!/usr/bin/env pnpm tsx
/**
 * Test Open Design Figma Exporter Functionality
 * ============================================
 * End-to-end functionality verification test suite for Open Design Figma Exporter & Token Compiler.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { exportFigmaArtifacts, generateW3CTokens, generateFigmaImportBundle } from './export-figma-artifacts.js';

function runFunctionalityTests() {
  console.log('🧪 Starting Open Design Figma Exporter Functionality Tests...\n');

  // Test 1: Validate W3C Token Generator Structure
  console.log('Test 1: Validating W3C Token Structure...');
  const tokens = generateW3CTokens();
  if (!tokens.color?.brand?.primary?.$value) {
    throw new Error('FAILED: Missing brand primary color value');
  }
  if (!tokens.spacing?.md?.$value) {
    throw new Error('FAILED: Missing spacing md value');
  }
  if (!tokens.typography?.heading1?.$value?.fontSize) {
    throw new Error('FAILED: Missing heading1 typography font size');
  }
  console.log('  ✅ W3C Tokens Structure is valid.');

  // Test 2: Validate Figma Import Bundle Schema & Auto-Layout
  console.log('\nTest 2: Validating Figma Import Bundle Schema...');
  const bundle = generateFigmaImportBundle(tokens);
  if (bundle.schema !== 'open-design-figma-bundle') {
    throw new Error(`FAILED: Expected schema open-design-figma-bundle, got ${bundle.schema}`);
  }
  if (!bundle.auto_layout?.desktop_frame?.width || bundle.auto_layout.desktop_frame.width !== 1440) {
    throw new Error('FAILED: Invalid auto-layout desktop frame configuration');
  }
  if (!Array.isArray(bundle.components) || bundle.components.length === 0) {
    throw new Error('FAILED: Components array is missing or empty');
  }
  console.log('  ✅ Figma Import Bundle Schema & Components are valid.');

  // Test 3: Export Artifact File Generation
  console.log('\nTest 3: Testing File Exporter Disk Generation...');
  const testOutputDir = path.resolve('dist/functionality-test-artifacts');
  exportFigmaArtifacts(testOutputDir);

  const expectedFiles = [
    'design_tokens.json',
    'figma_import_bundle.json',
    'open-design-export.od-figma.json'
  ];

  for (const file of expectedFiles) {
    const filePath = path.join(testOutputDir, file);
    if (!fs.existsSync(filePath)) {
      throw new Error(`FAILED: Expected artifact file not created: ${filePath}`);
    }
    const stat = fs.statSync(filePath);
    if (stat.size === 0) {
      throw new Error(`FAILED: Artifact file is empty (0 bytes): ${filePath}`);
    }
    // Verify JSON parseability
    const content = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(content);
    if (!parsed || typeof parsed !== 'object') {
      throw new Error(`FAILED: File content is not valid JSON object: ${filePath}`);
    }
  }
  console.log('  ✅ Artifact files generated, non-empty, and valid JSON.');

  console.log('\n🎉 ALL FUNCTIONALITY TESTS PASSED SUCCESSFULLY!\n');
}

runFunctionalityTests();
