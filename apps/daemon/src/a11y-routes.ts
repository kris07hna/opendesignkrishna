import { Router, type Request, type Response } from 'express';
import { execFile } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const a11yRouter: Router = Router();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const a11yScriptPath = path.resolve(__dirname, '../../../a11ymcp/run-audit.mjs');

a11yRouter.post('/audit', (req: Request, res: Response) => {
  const { url, html } = req.body || {};

  if (!url && !html) {
    return res.status(400).json({ error: 'Either "url" or "html" parameter is required.' });
  }

  const targetUrl = url || 'https://www.timesnownews.com/';

  execFile('node', [a11yScriptPath, targetUrl], { timeout: 60000 }, (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({
        ok: false,
        error: error.message,
        stderr: stderr || undefined,
        stdout: stdout || undefined
      });
    }

    return res.json({
      ok: true,
      rawOutput: stdout,
    });
  });
});
