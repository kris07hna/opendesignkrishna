import os
import json
import subprocess
import tempfile
import asyncio
from crawler.config import log, DEFAULT_MODEL


async def check_opencode() -> bool:
    try:
        res = subprocess.run(["opencode", "--version"], capture_output=True, text=True, timeout=5, shell=(os.name == 'nt'))
        return res.returncode == 0
    except Exception:
        return False

async def ask_opencode(prompt: str, model: str = DEFAULT_MODEL) -> str:
    log(f"Querying {model}...", "AI")
    
    # Use a temp file to avoid Windows CMD character limits ([WinError 206])
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".md") as f:
        f.write(prompt)
        tmp_path = f.name
        
    try:
        if os.name == 'nt':
            # Use shell=True behavior via create_subprocess_shell on Windows
            cmd_str = f'opencode run "Follow the instructions in the attached file." -m "{model}" -f "{tmp_path}"'
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "opencode", "run", "Follow the instructions in the attached file.", "-m", model, "-f", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                err_msg = stderr.decode('utf-8', errors='ignore').strip()
                log(f"AI Error: {err_msg}", "ERROR")
                return ""
            return stdout.decode('utf-8', errors='ignore')
        except asyncio.TimeoutError:
            log("AI Timeout: opencode call took longer than 120s.", "ERROR")
            try:
                proc.kill()
            except:
                pass
            return ""


    except Exception as e:
        log(f"AI Exception: {e}", "ERROR")
        return ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass


def extract_json_block(text: str) -> str:
    start = text.find("```json")
    if start != -1:
        end = text.find("```", start + 7)
        if end != -1:
            return text[start+7:end].strip()
    
    # Fallback to finding first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
        
    return text.strip()

async def synthesize_complex_goal(goal: str, page_state: dict, history: list) -> dict:
    """
    Advanced LLM prompt for multi-step reasoning.
    Takes the current IA structure, visual elements, and previous history
    to decide the next best action.
    """
    prompt = f"""
You are an expert UX researcher and crawler. Your overarching goal is: {goal}

Current Page URL: {page_state.get('url')}
Current Page Semantic Structure (IA):
{json.dumps(page_state.get('ia', {}), indent=2)}

Available Interactive Elements:
{json.dumps(page_state.get('elements', [])[:20], indent=2)}

Past Action History:
{json.dumps(history, indent=2)}

Based on UX principles, formulate the next single action to progress towards the goal.
Respond ONLY with a JSON object in this format:
{{
  "reasoning": "Explain why this action helps achieve the goal",
  "action": "CLICK" or "TYPE" or "WAIT" or "SCROLL" or "DONE",
  "target_selector": "CSS selector of the element to interact with (if applicable)",
  "text_to_type": "Text to type (if action is TYPE)"
}}
"""
    response = await ask_opencode(prompt)
    json_text = extract_json_block(response)
    try:
        return json.loads(json_text)
    except Exception as e:
        log(f"Failed to parse LLM JSON: {e}", "ERROR")
        return {"action": "CLICK_NAV", "reasoning": "Fallback to heuristic navigation"}
