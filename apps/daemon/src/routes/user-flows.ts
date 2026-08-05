import type { Express, Request, Response } from 'express';
import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import type { UserFlowCrawlRequest } from '@open-design/contracts';
import type { RouteDeps } from '../server-context.js';
import { getProject } from '../db.js';
import { resolveProjectDir } from '../projects.js';

export interface RegisterUserFlowRoutesDeps extends RouteDeps<'db' | 'http' | 'paths'> {}

/**
 * Resolves the workspace root directory (where crawl_map_ai.py lives).
 * The daemon cwd during development is the monorepo root; in production
 * the daemon binary is in apps/daemon/dist, so we walk up to find the
 * script. Falls back to process.cwd() if the script is found there directly.
 */
function resolveWorkspaceRoot(): string {
  const candidates = [
    process.cwd(),
    path.resolve(process.cwd(), '..', '..'),
    path.resolve(import.meta.url ? new URL(import.meta.url).pathname : __dirname,
      '..', '..', '..', '..'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(path.join(candidate, 'crawl_map_ai.py'))) {
      return candidate;
    }
  }
  return process.cwd();
}

/**
 * Returns the python executable inside the project .venv, or falls back
 * to the system python if the venv does not yet exist.
 */
function resolvePythonBin(workspaceRoot: string): string {
  const venvPython = process.platform === 'win32'
    ? path.join(workspaceRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(workspaceRoot, '.venv', 'bin', 'python');

  if (fs.existsSync(venvPython)) {
    return venvPython;
  }

  // Fallback to system python
  return process.platform === 'win32' ? 'python' : 'python3';
}

/**
 * Streams real-time crawl logs to the client via Server-Sent Events so the
 * UI can display live progress without polling. The SSE channel stays open
 * until the subprocess exits, then sends a final `done` event with the
 * output file paths or an `error` event on failure.
 */
function handleStreamCrawl(
  req: Request,
  res: Response,
  projectId: string,
  url: string,
  goal: string,
  maxDepth: number,
  outputDir: string,
  pythonBin: string,
  crawlerScript: string,
  workspaceRoot: string,
  model?: string,
): void {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  const sendEvent = (event: string, data: unknown) => {
    if (res.writableEnded) return;
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  };

  const args = [
    crawlerScript,
    '--url', url.trim(),
    '--goal', goal.trim(),
    '--max-steps', String(maxDepth),
    '--output-dir', outputDir,
  ];

  if (model && model.trim()) {
    args.push('--model', model.trim());
  }

  sendEvent('start', {
    message: `Starting crawl of ${url} (depth ${maxDepth})`,
    url, goal, maxDepth,
  });

  // crawlDone is set to true before res.end() so the res.on('close')
  // handler knows not to kill the child (it already exited cleanly).
  let crawlDone = false;

  const venvDir = path.join(workspaceRoot, '.venv');
  const venvBinDir = process.platform === 'win32'
    ? path.join(venvDir, 'Scripts')
    : path.join(venvDir, 'bin');

  const childEnv: Record<string, string | undefined> = { ...process.env };
  if (fs.existsSync(venvBinDir)) {
    childEnv.VIRTUAL_ENV = venvDir;
    childEnv.PATH = `${venvBinDir}${path.delimiter}${process.env.PATH || ''}`;
  }

  const child = spawn(pythonBin, args, {
    cwd: workspaceRoot,
    env: childEnv,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  console.log(`[UserFlow:${projectId}] Spawned PID ${child.pid ?? 'unknown'} → ${pythonBin}`);

  let stderrBuffer = '';

  child.stdout.on('data', (chunk: Buffer) => {
    const text = chunk.toString();
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (trimmed) {
        console.log(`[UserFlow:${projectId}] ${trimmed}`);
        sendEvent('log', { line: trimmed });

        if (trimmed.startsWith('[STEP ')) {
          sendEvent('step', { kind: 'step', text: trimmed });
        } else if (trimmed.startsWith('[AI THINKING]')) {
          sendEvent('step', { kind: 'thinking', text: trimmed.replace('[AI THINKING]', '').trim() });
        } else if (trimmed.startsWith('[ACTION]')) {
          sendEvent('step', { kind: 'action', text: trimmed.replace('[ACTION]', '').trim() });
        } else if (trimmed.startsWith('[SHOT]')) {
          sendEvent('step', { kind: 'shot', text: trimmed.replace('[SHOT]', '').trim() });
        } else if (trimmed.startsWith('[WHITEBOARD]')) {
          sendEvent('step', { kind: 'whiteboard', text: trimmed.replace('[WHITEBOARD]', '').trim() });
        }
      }
    }
  });

  child.stderr.on('data', (chunk: Buffer) => {
    stderrBuffer += chunk.toString();
    for (const line of chunk.toString().split('\n')) {
      const trimmed = line.trim();
      if (trimmed) {
        console.error(`[UserFlow:${projectId}] STDERR: ${trimmed}`);
        sendEvent('log', { line: `[stderr] ${trimmed}` });
      }
    }
  });

  // Heartbeat to keep the SSE connection alive across proxies
  const heartbeat = setInterval(() => {
    if (!res.writableEnded) {
      res.write(': ping\n\n');
    }
  }, 15000);

  child.on('close', (code, signal) => {
    clearInterval(heartbeat);
    if (res.writableEnded) return;

    // null exit code on Windows means the process was killed by a signal
    // (e.g. SIGTERM from our own cleanup handler or an OS kill).
    const exitedClean = code === 0;
    const killedBySelf = (code === null) && crawlDone;

    if (!exitedClean && !killedBySelf) {
      const errSnippet = stderrBuffer.slice(-600).trim();
      const codeDesc = code !== null ? `exit code ${code}` : `signal ${signal ?? 'SIGTERM'}`;
      console.error(`[UserFlow:${projectId}] Crawler exited with ${codeDesc}. stderr: ${errSnippet || '(none)'}`);
      sendEvent('error', {
        message: `Crawl failed (${codeDesc})`,
        detail: errSnippet
          || 'No error output was captured. Check that Playwright browsers are installed:\n  .venv\\Scripts\\python.exe -m playwright install chromium',
      });
      crawlDone = true;
      res.end();
      return;
    }

    if (!exitedClean) return; // already handled above or intentionally killed

    const sitemapPath = path.join(outputDir, 'sitemap_ai.json');
    const sketchPath  = path.join(outputDir, 'sitemap_flow.sketch.json');

    if (!fs.existsSync(sketchPath)) {
      sendEvent('error', {
        message: 'Crawl completed but whiteboard file was not generated.',
        detail: 'Run the crawler manually to see the full error:\n  .venv\\Scripts\\python.exe crawl_map_ai.py --url <URL> --goal <GOAL>',
      });
      crawlDone = true;
      res.end();
      return;
    }

    sendEvent('done', {
      message: 'User flow whiteboard generated successfully.',
      sitemapPath: 'screenshots_ai/sitemap_ai.json',
      sketchPath:  'screenshots_ai/sitemap_flow.sketch.json',
      absoluteSketchPath: sketchPath,
    });
    crawlDone = true;
    res.end();
  });

  child.on('error', (err) => {
    clearInterval(heartbeat);
    console.error(`[UserFlow:${projectId}] Spawn error:`, err);
    sendEvent('error', {
      message: `Failed to start crawler: ${err.message}`,
      detail:
        'Ensure the Python virtual environment is set up correctly.\n' +
        'Run: .venv\\Scripts\\python.exe -m pip install playwright && ' +
        '.venv\\Scripts\\python.exe -m playwright install chromium',
    });
    crawlDone = true;
    res.end();
  });

  // Only kill the child if the RESPONSE stream closes (browser tab closed /
  // navigation away), NOT when the REQUEST body stream closes (which fires
  // immediately after Express body-parser consumes the POST body).
  res.on('close', () => {
    clearInterval(heartbeat);
    if (!crawlDone && !child.killed) {
      console.log(`[UserFlow:${projectId}] Client disconnected – killing crawler PID ${child.pid}`);
      child.kill();
    }
  });
}

export function registerUserFlowRoutes(
  app: Express,
  ctx: RegisterUserFlowRoutesDeps,
) {
  const { db } = ctx;
  const { sendApiError } = ctx.http;
  const { PROJECTS_DIR } = ctx.paths;

  const workspaceRoot = resolveWorkspaceRoot();
  const crawlerScript = path.join(workspaceRoot, 'crawl_map_ai.py');
  const pythonBin = resolvePythonBin(workspaceRoot);

  console.log(`[UserFlow] workspace root : ${workspaceRoot}`);
  console.log(`[UserFlow] python binary  : ${pythonBin}`);
  console.log(`[UserFlow] crawler script : ${crawlerScript}`);

  // ----- POST /api/projects/:id/user-flows/crawl (SSE streaming) ---------------
  app.post('/api/projects/:id/user-flows/crawl', (req, res) => {
    try {
      const projectId = req.params.id;
      const project = getProject(db, projectId);
      if (!project) {
        return sendApiError(res, 404, 'PROJECT_NOT_FOUND', 'Project not found');
      }

      const body = (req.body ?? {}) as Partial<UserFlowCrawlRequest>;
      const rawUrl = body.url;
      const rawGoal = body.goal;
      const maxDepth = body.maxDepth ?? 1;
      const model = body.model;

      if (!rawUrl || typeof rawUrl !== 'string' || !rawUrl.trim()) {
        return sendApiError(res, 400, 'BAD_REQUEST', 'url is required');
      }
      if (!rawGoal || typeof rawGoal !== 'string' || !rawGoal.trim()) {
        return sendApiError(res, 400, 'BAD_REQUEST', 'goal is required');
      }

      let targetUrl = rawUrl.trim();
      if (!/^https?:\/\//i.test(targetUrl)) {
        targetUrl = `https://${targetUrl}`;
      }
      const goal = rawGoal.trim();

      if (!fs.existsSync(crawlerScript)) {
        return sendApiError(
          res, 500, 'SETUP_INCOMPLETE',
          `Crawler script not found at ${crawlerScript}. Run pnpm bootstrap to set up the Python environment.`
        );
      }

      const projectRoot = resolveProjectDir(PROJECTS_DIR, projectId, project.metadata);
      const outputDir   = path.join(projectRoot, 'screenshots_ai');

      handleStreamCrawl(
        req, res,
        projectId, targetUrl, goal, maxDepth,
        outputDir, pythonBin, crawlerScript, workspaceRoot,
        model,
      );
    } catch (caught) {
      if (!res.headersSent) {
        return sendApiError(
          res, 500, 'INTERNAL_ERROR',
          caught instanceof Error ? caught.message : String(caught)
        );
      }
    }
  });

  // ----- GET /api/projects/:id/user-flows/status (lightweight check) -----------
  app.get('/api/projects/:id/user-flows/status', (req, res) => {
    try {
      const projectId = req.params.id;
      const project = getProject(db, projectId);
      if (!project) {
        return sendApiError(res, 404, 'PROJECT_NOT_FOUND', 'Project not found');
      }

      const projectRoot = resolveProjectDir(PROJECTS_DIR, projectId, project.metadata);
      const sketchPath  = path.join(projectRoot, 'screenshots_ai', 'sitemap_flow.sketch.json');
      const sitemapPath = path.join(projectRoot, 'screenshots_ai', 'sitemap_ai.json');

      const hasSketch  = fs.existsSync(sketchPath);
      const hasSitemap = fs.existsSync(sitemapPath);

      res.json({
        ready: hasSketch,
        sketchPath:  hasSketch  ? 'screenshots_ai/sitemap_flow.sketch.json' : null,
        sitemapPath: hasSitemap ? 'screenshots_ai/sitemap_ai.json'          : null,
        pythonReady: fs.existsSync(pythonBin.includes('venv') ? pythonBin : ''),
        crawlerReady: fs.existsSync(crawlerScript),
      });
    } catch (caught) {
      return sendApiError(
        res, 500, 'INTERNAL_ERROR',
        caught instanceof Error ? caught.message : String(caught)
      );
    }
  });
}
