export interface UserFlowCrawlRequest {
  url: string;
  goal: string;
  mode?: 'flow' | 'spider' | 'ux-ia';
  viewport?: 'both' | 'desktop-only' | 'mobile-only';
  fullPage?: boolean;
  maxSteps?: number;
  maxDepth?: number;
  model?: string;
  noAi?: boolean;
  noScreenshots?: boolean;
}

export interface UserFlowCrawlResponse {
  ok: boolean;
  message: string;
  sitemapPath?: string;
  sketchPath?: string;
}
