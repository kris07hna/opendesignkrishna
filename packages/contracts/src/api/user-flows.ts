export interface UserFlowCrawlRequest {
  url: string;
  goal: string;
  maxDepth?: number;
  model?: string;
}

export interface UserFlowCrawlResponse {
  ok: boolean;
  message: string;
  sitemapPath?: string;
  sketchPath?: string;
}
