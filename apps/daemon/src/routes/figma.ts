import type { Express, Request, Response } from 'express';
import type { RouteDeps } from '../server-context.js';
import type { ByokChatProviderConfig } from '@open-design/contracts';

export interface RegisterFigmaRoutesDeps extends RouteDeps<'http'> {}

const UX_AUDIT_SYSTEM_PROMPT = `You are an expert UX Audit jury consisting of 5 specialists:
1. Designer: Audits visual layout, composition, alignment, and hierarchy.
2. Critic: Audits usability, flow relevance, contrast, and readability.
3. Brand: Audits design token compliance, color rules, and overall polish.
4. Accessibility: Audits WCAG contrast ratios, focus rings, and screen-reader hierarchy.
5. Copy: Audits typography copy, tone of voice, brevity, and error messaging.

Analyze the serialized Figma node structure provided by the user.

Perform a thorough audit from the perspective of each specialist. For each specialist, calculate an individual score from 0.0 to 10.0 and provide 1-3 specific recommendations or issues (labeled as must-fix if critical, or suggestions otherwise).
Compute an overall composite score as the weighted average:
Composite = Designer * 0.0 + Critic * 0.4 + Brand * 0.2 + Accessibility * 0.2 + Copy * 0.2

You MUST return a valid JSON object matching the following TypeScript schema structure. Return ONLY the JSON object, with no markdown fences, code blocks, or preamble:

{
  "composite": number,
  "panelists": {
    "designer": {
      "score": number,
      "notes": string,
      "mustFix": string[]
    },
    "critic": {
      "score": number,
      "notes": string,
      "mustFix": string[]
    },
    "brand": {
      "score": number,
      "notes": string,
      "mustFix": string[]
    },
    "accessibility": {
      "score": number,
      "notes": string,
      "mustFix": string[]
    },
    "copy": {
      "score": number,
      "notes": string,
      "mustFix": string[]
    }
  }
}
`;

async function callLLM(
  provider: { protocol: string; apiKey: string; baseUrl: string; model: string },
  system: string,
  user: string,
  images?: Array<{ name: string; dataUri: string }>,
): Promise<string> {
  let url = '';
  const headers: Record<string, string> = {
    'content-type': 'application/json',
  };
  let body: any = {};

  const apiKey = provider.apiKey || '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';
  const baseUrl = provider.baseUrl || '';

  if (provider.protocol === 'anthropic') {
    url = `${baseUrl.replace(/\/+$/, '')}/messages`;
    headers['x-api-key'] = apiKey;
    headers['anthropic-version'] = '2023-06-01';
    
    const contentBlocks: any[] = [{ type: 'text', text: user }];
    for (const img of images || []) {
      const match = /^data:(image\/[a-zA-Z+]+);base64,(.+)$/.exec(img.dataUri || '');
      if (match) {
        contentBlocks.push({
          type: 'image',
          source: { type: 'base64', media_type: match[1], data: match[2] }
        });
      }
    }

    body = {
      model: provider.model || 'claude-3-5-sonnet-20241022',
      max_tokens: 4096,
      system,
      messages: [{ role: 'user', content: contentBlocks }],
    };
  } else if (provider.protocol === 'google') {
    const model = encodeURIComponent(provider.model || 'gemini-2.5-flash');
    url = `${baseUrl.replace(/\/+$/, '')}/v1beta/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
    if (apiKey) {
      headers['X-goog-api-key'] = apiKey;
    }
    
    const parts: any[] = [{ text: user }];
    for (const img of images || []) {
      const match = /^data:(image\/[a-zA-Z+]+);base64,(.+)$/.exec(img.dataUri || '');
      if (match) {
        parts.push({
          inlineData: { mimeType: match[1], data: match[2] }
        });
      }
    }

    body = {
      systemInstruction: { role: 'system', parts: [{ text: system }] },
      contents: [{ role: 'user', parts }],
      generationConfig: { responseMimeType: 'application/json' },
    };
  } else if (provider.protocol === 'cloudflare') {
    const accountId = '25920c1df3b7ec0a85ee2032cd681398';
    const cfKey = apiKey || '';
    url = `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/v1/chat/completions`;

    headers['authorization'] = `Bearer ${cfKey}`;

    const contentArray: any[] = [{ type: 'text', text: user }];
    for (const img of images || []) {
      contentArray.push({
        type: 'image_url',
        image_url: { url: img.dataUri }
      });
    }

    body = {
      model: provider.model || '@cf/openai/gpt-oss-120b',
      max_tokens: 4096,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: contentArray.length === 1 ? user : contentArray },
      ],
    };
  } else {
    // OpenAI, Ollama, OpenRouter
    const path = '/chat/completions';
    const normalizedBaseUrl = baseUrl.replace(/\/+$/, '');
    url = /\/v\d+(\/|$)/.test(normalizedBaseUrl)
      ? `${normalizedBaseUrl}${path}`
      : `${normalizedBaseUrl}/v1${path}`;

    if (apiKey) {
      headers['authorization'] = `Bearer ${apiKey}`;
    }

    const contentArray: any[] = [{ type: 'text', text: user }];
    for (const img of images || []) {
      contentArray.push({
        type: 'image_url',
        image_url: { url: img.dataUri }
      });
    }

    body = {
      model: provider.model || 'google/gemini-2.5-flash',
      max_tokens: 4096,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: contentArray.length === 1 ? user : contentArray },
      ],
    };
  }

  let resp = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  // Automatic retry with fallback model on 429 (rate-limited) or 503 (high demand)
  if (!resp.ok && (resp.status === 429 || resp.status === 503) && provider.protocol === 'openrouter') {
    console.warn(`[callLLM] model ${provider.model} returned ${resp.status}, retrying with google/gemini-2.5-flash...`);
    body.model = 'google/gemini-2.5-flash';
    resp = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
  }

  if (!resp.ok) {
    const errorText = await resp.text().catch(() => '');
    throw new Error(`LLM provider ${provider.protocol} returned ${resp.status}: ${errorText}`);
  }

  const json = (await resp.json()) as any;

  if (provider.protocol === 'anthropic') {
    const block = (json?.content || []).find((b: any) => b?.type === 'text');
    return block?.text ?? '';
  } else if (provider.protocol === 'google') {
    const parts = json?.candidates?.[0]?.content?.parts;
    if (Array.isArray(parts)) {
      return parts.map((p: any) => (p && typeof p.text === 'string' ? p.text : '')).join('');
    }
    return '';
  } else {
    return json?.choices?.[0]?.message?.content ?? '';
  }
}

export function registerFigmaRoutes(app: Express, ctx: RegisterFigmaRoutesDeps) {
  const { sendApiError } = ctx.http;

  app.post('/api/figma/audit', async (req: Request, res: Response) => {
    try {
      const { elements, byokProvider } = req.body as {
        elements: unknown;
        byokProvider: ByokChatProviderConfig;
      };

      if (!elements) {
        return sendApiError(res, 400, 'MISSING_ELEMENTS', 'Figma elements payload is required');
      }

      if (!byokProvider || !byokProvider.protocol || !byokProvider.model) {
        return sendApiError(
          res,
          400,
          'MISSING_PROVIDER',
          'A valid LLM provider (protocol, model, and apiKey if required) is required',
        );
      }

      const elementsStr = typeof elements === 'string' ? elements : JSON.stringify(elements, null, 2);

      let baseUrl = byokProvider.baseUrl || '';
      if (!baseUrl) {
        if (byokProvider.protocol === 'openrouter') {
          baseUrl = 'https://openrouter.ai/api/v1';
        } else if (byokProvider.protocol === 'openai') {
          baseUrl = 'https://api.openai.com/v1';
        } else if (byokProvider.protocol === 'anthropic') {
          baseUrl = 'https://api.anthropic.com/v1';
        } else if (byokProvider.protocol === 'google') {
          baseUrl = 'https://generativelanguage.googleapis.com';
        }
      }

      const rawReport = await callLLM(
        {
          protocol: byokProvider.protocol,
          apiKey: byokProvider.apiKey,
          baseUrl,
          model: byokProvider.model,
        },
        UX_AUDIT_SYSTEM_PROMPT,
        `Figma design element selection:\n\n${elementsStr}`,
      );

      let cleanJsonText = rawReport.trim();
      if (cleanJsonText.startsWith('```')) {
        cleanJsonText = cleanJsonText.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
      }

      let parsedReport;
      try {
        parsedReport = JSON.parse(cleanJsonText);
      } catch (e) {
        const match = /\{[\s\S]*\}/.exec(cleanJsonText);
        if (match) {
          parsedReport = JSON.parse(match[0]);
        } else {
          throw new Error(`Failed to parse LLM JSON report. Raw output: ${rawReport}`);
        }
      }

      res.status(200).json(parsedReport);
    } catch (err: any) {
      console.error('[figma-audit] failed', err);
      sendApiError(res, 500, 'AUDIT_FAILED', err?.message || 'UX Audit execution failed');
    }
  });

  // --- AI Persona Generator ---
  app.post('/api/figma/persona', async (req: Request, res: Response) => {
    try {
      const { prompt, byokProvider } = req.body as { prompt: string; byokProvider: ByokChatProviderConfig };
      if (!prompt) return sendApiError(res, 400, 'MISSING_PROMPT', 'Prompt is required');
      if (!byokProvider || !byokProvider.protocol) return sendApiError(res, 400, 'MISSING_PROVIDER', 'BYOK provider is required');

      const system = `You are a UX Researcher. Generate a structured User Persona object based on the user prompt.
Return ONLY a JSON object matching this schema with no markdown:
{
  "name": "string",
  "role": "string",
  "demographics": "string",
  "goals": ["string", "string"],
  "frustrations": ["string", "string"],
  "quote": "string"
}`;

      let baseUrl = byokProvider.baseUrl || '';
      if (!baseUrl) {
        if (byokProvider.protocol === 'openrouter') baseUrl = 'https://openrouter.ai/api/v1';
        else if (byokProvider.protocol === 'openai') baseUrl = 'https://api.openai.com/v1';
        else if (byokProvider.protocol === 'anthropic') baseUrl = 'https://api.anthropic.com/v1';
        else if (byokProvider.protocol === 'google') baseUrl = 'https://generativelanguage.googleapis.com';
      }

      const raw = await callLLM(
        {
          protocol: byokProvider.protocol,
          apiKey: byokProvider.apiKey || '',
          baseUrl,
          model: byokProvider.model || '',
        },
        system,
        prompt,
      );
      const clean = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
      res.status(200).json(JSON.parse(clean));
    } catch (err: any) {
      console.error('[figma-persona] failed', err);
      sendApiError(res, 500, 'PERSONA_FAILED', err?.message || 'Persona generation failed');
    }
  });

  // --- AI Industry-Grade Multimodal Flowchart Generator ---
  app.post('/api/figma/flow', async (req: Request, res: Response) => {
    try {
      const { task, elements, images, byokProvider } = req.body as {
        task?: string;
        elements?: unknown;
        images?: Array<{ name: string; dataUri: string }>;
        byokProvider: ByokChatProviderConfig;
      };
      if (!task && !elements && (!images || images.length === 0)) {
        return sendApiError(res, 400, 'MISSING_INPUT', 'Task description, Figma elements, or screen images are required');
      }
      if (!byokProvider || !byokProvider.protocol) return sendApiError(res, 400, 'MISSING_PROVIDER', 'BYOK provider is required');

      const system = `You are a Principal Product Architect. Analyze the provided visual UI screen images, Figma node elements, and user goals to reverse-engineer an industry-grade, highly professional User Flow diagram.

Inspect each visual screen image carefully. Identify:
1. Exact Screen Names & Titles.
2. User Action Triggers (e.g. "Clicks 'Pay Now' Button", "Enters Password").
3. System State Changes & Decision Nodes (e.g. "Payment Approved?", "Form Valid?").
4. Clear Directional Step Transitions (Screen ➔ Trigger ➔ Decision ➔ Next Screen / Error Screen).

Return ONLY a valid JSON object matching this schema with no markdown or preamble:
{
  "title": "string",
  "theme": "professional",
  "steps": [
    {
      "id": "step_1",
      "type": "screen",
      "label": "Sign In Screen",
      "screenName": "Exact Name of Frame/Image",
      "description": "User enters credentials.",
      "trigger": "Clicks 'Sign In' Button",
      "nextStepId": "step_2"
    },
    {
      "id": "step_2",
      "type": "decision",
      "label": "Valid Credentials?",
      "yesTarget": "step_3",
      "noTarget": "step_error"
    },
    {
      "id": "step_3",
      "type": "screen",
      "label": "Dashboard",
      "screenName": "Dashboard Frame",
      "description": "Main user homepage.",
      "trigger": "Navigates to Settings",
      "nextStepId": "step_4"
    }
  ]
}`;

      let baseUrl = byokProvider.baseUrl || '';
      if (!baseUrl) {
        if (byokProvider.protocol === 'openrouter') baseUrl = 'https://openrouter.ai/api/v1';
        else if (byokProvider.protocol === 'openai') baseUrl = 'https://api.openai.com/v1';
        else if (byokProvider.protocol === 'anthropic') baseUrl = 'https://api.anthropic.com/v1';
        else if (byokProvider.protocol === 'google') baseUrl = 'https://generativelanguage.googleapis.com';
      }

      let userPrompt = `Generate a realistic, industry-grade user flow diagram.\nGoal/Context: ${task || 'Full screen flow'}`;
      if (elements) {
        const elementsStr = typeof elements === 'string' ? elements : JSON.stringify(elements, null, 2);
        userPrompt += `\n\nFigma Node Elements Structure:\n${elementsStr}`;
      }

      const raw = await callLLM(
        {
          protocol: byokProvider.protocol,
          apiKey: byokProvider.apiKey || '',
          baseUrl,
          model: byokProvider.model || '',
        },
        system,
        userPrompt,
        images,
      );
      const clean = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
      res.status(200).json(JSON.parse(clean));
    } catch (err: any) {
      console.error('[figma-flow] failed', err);
      sendApiError(res, 500, 'FLOW_FAILED', err?.message || 'User flow generation failed');
    }
  });

  // --- AI UX Copywriter ---
  app.post('/api/figma/copy', async (req: Request, res: Response) => {
    try {
      const { text, context, byokProvider } = req.body as { text: string; context?: string; byokProvider: ByokChatProviderConfig };
      if (!text) return sendApiError(res, 400, 'MISSING_TEXT', 'Text is required');
      if (!byokProvider || !byokProvider.protocol) return sendApiError(res, 400, 'MISSING_PROVIDER', 'BYOK provider is required');

      const system = `You are a Senior UX Writer. Suggest 4 high-converting, clear alternatives for the provided text.
Return ONLY a JSON object with no markdown:
{
  "original": "string",
  "suggestions": [
    { "category": "Action-Oriented CTA", "text": "string" },
    { "category": "Clear & Direct", "text": "string" },
    { "category": "Friendly & Conversational", "text": "string" },
    { "category": "Concise Microcopy", "text": "string" }
  ]
}`;

      let baseUrl = byokProvider.baseUrl || '';
      if (!baseUrl) {
        if (byokProvider.protocol === 'openrouter') baseUrl = 'https://openrouter.ai/api/v1';
        else if (byokProvider.protocol === 'openai') baseUrl = 'https://api.openai.com/v1';
        else if (byokProvider.protocol === 'anthropic') baseUrl = 'https://api.anthropic.com/v1';
        else if (byokProvider.protocol === 'google') baseUrl = 'https://generativelanguage.googleapis.com';
      }

      const raw = await callLLM(
        {
          protocol: byokProvider.protocol,
          apiKey: byokProvider.apiKey || '',
          baseUrl,
          model: byokProvider.model || '',
        },
        system,
        `Text: "${text}"\nContext: ${context || 'General UI'}`,
      );
      const clean = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
      res.status(200).json(JSON.parse(clean));
    } catch (err: any) {
      console.error('[figma-copy] failed', err);
      sendApiError(res, 500, 'COPY_FAILED', err?.message || 'Copy generation failed');
    }
  });

  // --- Proxy Image Helper ---
  app.get('/api/figma/proxy-image', async (req: Request, res: Response) => {
    try {
      const { url } = req.query as { url?: string };
      if (!url) return sendApiError(res, 400, 'MISSING_URL', 'URL is required');

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch image: ${response.statusText}`);
      }
      const buffer = await response.arrayBuffer();
      const contentType = response.headers.get('content-type') || 'image/png';
      const base64 = Buffer.from(buffer).toString('base64');
      const dataUri = `data:${contentType};base64,${base64}`;
      res.status(200).json({ dataUri });
    } catch (err: any) {
      console.error('[figma-proxy-image] failed', err);
      sendApiError(res, 500, 'PROXY_FAILED', err?.message || 'Failed to proxy image');
    }
  });
}

