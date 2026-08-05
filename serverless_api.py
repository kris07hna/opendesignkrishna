import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from firecrawl import FirecrawlApp
import google.generativeai as genai

# Initialize FastAPI app
app = FastAPI(title="Open Design AI Mapper API")

# Initialize SDKs (Make sure FIRECRAWL_API_KEY and GEMINI_API_KEY are in your environment)
firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY", "fc-44355c694b6b41f4bd4f99cfeea531d9"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY"))

class MapRequest(BaseModel):
    url: str
    limit: int = 5

@app.post("/api/map")
async def map_website_flow(req: MapRequest):
    """
    1. Crawls the target URL via Firecrawl to grab full-page screenshots.
    2. Sends the screenshots to Gemini Flash for Open Design Thinking UX analysis.
    """
    print(f"Starting Firecrawl for {req.url}...")
    
    # STEP 1: Get Screenshots via Firecrawl (Bypassing local Playwright)
    try:
        crawl_result = firecrawl.crawl_url(
            req.url,
            limit=req.limit,
            scrape_options={
                'formats': ['screenshot'],
                'screenshot': {'fullPage': True}
            },
            poll_interval=5
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firecrawl failed: {str(e)}")

    # Extract screenshot URLs
    screenshots = []
    if hasattr(crawl_result, 'data') and crawl_result.data:
        for page in crawl_result.data:
            screenshot_url = getattr(page, 'screenshot', None)
            source_url = getattr(page.metadata, 'source_url', 'Unknown URL') if hasattr(page, 'metadata') else 'Unknown URL'
            if screenshot_url:
                screenshots.append({"url": source_url, "image_url": screenshot_url})

    if not screenshots:
        raise HTTPException(status_code=404, detail="No screenshots were captured.")

    print(f"Captured {len(screenshots)} screenshots. Running AI Analysis...")

    # STEP 2: Pass screenshots to the LLM for "Open Design thinking"
    # We ask the model to analyze the user flow across the captured screens.
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    You are a Senior UX Researcher (Open Design Thinking).
    I have mapped a website starting at {req.url}. 
    Here are the URLs that were discovered and their screenshot image links:
    {screenshots}
    
    Please analyze these screens and provide:
    1. A summary of the core user flow (what is the user trying to accomplish?).
    2. Any UX friction points or design inconsistencies across the pages.
    3. A JSON representation of the sitemap graph mapping how these pages connect.
    """
    
    try:
        # Note: For production, you would fetch the image bytes and pass them to Gemini directly 
        # using genai.types.Part.from_uri or raw bytes. Here we pass the URLs for the model to analyze.
        response = model.generate_content(prompt)
        ai_analysis = response.text
    except Exception as e:
        ai_analysis = f"AI Analysis Failed: {str(e)}"

    # Return the final JSON to your frontend web application
    return {
        "status": "success",
        "crawled_pages": len(screenshots),
        "screenshots": screenshots,
        "design_thinking_analysis": ai_analysis
    }

# To run locally: uvicorn serverless_api:app --reload
