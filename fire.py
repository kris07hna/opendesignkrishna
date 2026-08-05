from firecrawl import FirecrawlApp

# Initialize the app with your API key
app = FirecrawlApp(api_key="fc-44355c694b6b41f4bd4f99cfeea531d9")

target_url = 'https://www.theguardian.com/international'
print(f"Starting crawl for: {target_url}")

# Crawl the website (this will follow links and scrape all pages)
crawl_result = app.crawl_url(
    target_url,
    limit=100, # Maximum number of pages to crawl (adjust as needed)
    crawl_entire_domain=True, # Allows crawling outside of /international/
    allow_subdomains=True, # Allows crawling different subdomains (e.g. sport.theguardian.com)
    scrape_options={
        'formats': ['screenshot'],
        'screenshot': {'fullPage': True}
    },
    poll_interval=10 # Checks the job status every 10 seconds until complete
)

print("\nCrawl Completed! Here are the results:")

# Iterate through all the pages it found and output their screenshot URLs
if hasattr(crawl_result, 'data') and crawl_result.data:
    for page in crawl_result.data:
        url = getattr(page.metadata, 'source_url', 'Unknown URL') if hasattr(page, 'metadata') and page.metadata else 'Unknown URL'
        screenshot = getattr(page, 'screenshot', 'No screenshot found')
        
        print(f"\nPage URL: {url}")
        print(f"Screenshot URL: {screenshot}")
else:
    print(crawl_result)
