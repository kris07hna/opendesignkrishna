#!/usr/bin/env python3
"""
Open Design -> Figma REST API Direct Sync
========================================
Pushes workflow status updates, design token summaries, and link references directly to target
Figma files via Figma's official REST API endpoints (GET /v1/files/{key}, POST /v1/files/{key}/comments).
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse

FIGMA_API_BASE = "https://api.figma.com/v1"

def sync_to_figma(file_key, token, bundle_path, comment_message=None):
    if not token or not file_key:
        print("⚠️ FIGMA_ACCESS_TOKEN or FIGMA_FILE_KEY missing. Skipping direct REST API push.")
        return False

    print(f"🔄 Connecting to Figma REST API for file: {file_key}...")
    headers = {
        "X-Figma-Token": token,
        "Content-Type": "application/json"
    }

    # Step 1: Verify access to Figma file
    req = urllib.request.Request(f"{FIGMA_API_BASE}/files/{file_key}?depth=1", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            file_name = data.get("name", "Figma File")
            print(f"✅ Verified Figma File: '{file_name}' (Last Modified: {data.get('lastModified')})")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error connecting to Figma API: {e.code} {e.reason}")
        return False
    except Exception as e:
        print(f"❌ Error querying Figma API: {e}")
        return False

    # Step 2: Post status comment on Figma canvas
    if os.path.exists(bundle_path):
        with open(bundle_path, 'r', encoding='utf-8') as f:
            bundle = json.load(f)
        page_count = len(bundle.get("pages", []))
    else:
        page_count = 1

    msg = comment_message or f"🚀 [Open Design GitHub Action] Automated UI Flow & Design Tokens sync completed.\n- Mapped Pages: {page_count}\n- Figma Plugin Artifact Bundle ready for instant import."

    comment_url = f"{FIGMA_API_BASE}/files/{file_key}/comments"
    payload = json.dumps({"message": msg}).encode('utf-8')
    comment_req = urllib.request.Request(comment_url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(comment_req) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            comment_id = result.get("id")
            print(f"✅ Successfully posted update comment to Figma canvas! (Comment ID: {comment_id})")
            return True
    except Exception as e:
        print(f"⚠️ Failed to post comment to Figma API: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Open Design Figma REST API Direct Sync")
    parser.add_argument("--file-key", default=os.getenv("FIGMA_FILE_KEY"), help="Figma target file key")
    parser.add_argument("--token", default=os.getenv("FIGMA_ACCESS_TOKEN"), help="Figma access token")
    parser.add_argument("--bundle", default="screenshots_ai/figma_artifacts/figma_import_bundle.json", help="Path to Figma import bundle")
    parser.add_argument("--message", default=None, help="Custom comment message")
    args = parser.parse_args()

    sync_to_figma(args.file_key, args.token, args.bundle, args.message)

if __name__ == "__main__":
    main()
