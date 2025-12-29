#!/usr/bin/env python3
"""
Pluribus Multi-Phase Experiment CLI
Phase 1: Decode Season 1 through 5 analytical lenses
Phase 2: Generate Season 2 pitches from decoded understanding
Rewrite: Transform unified brief into polished curator's essay

Usage:
    ./pluribus_decode.py              # Runs with venv automatically
    ./pluribus_decode.py --phase 2    # Run generation phase
    ./pluribus_decode.py --rewrite    # Rewrite unified brief (one model at a time)
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ============================================================================
# VENV AUTO-ACTIVATION
# ============================================================================

def ensure_venv():
    """Ensure we're running in the virtual environment"""
    base_dir = Path(__file__).parent.parent  # SOCIAL_MEDIA_DRAFTS
    venv_python = base_dir / "venv" / "bin" / "python"

    # Check if we're already in venv
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return  # Already in venv

    # Check if venv exists
    if not venv_python.exists():
        print(f"Error: Virtual environment not found at {venv_python}")
        print("Create it with: python3 -m venv venv && pip install requests python-dotenv")
        sys.exit(1)

    # Re-execute with venv python
    print(f"Activating venv: {venv_python}")
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)


# Run venv check before imports that need it
ensure_venv()

import requests
from dotenv import load_dotenv

# ============================================================================
# CONFIGURATION
# ============================================================================

MODELS = {
    "gpt": {
        "id": "openai/gpt-5.2-chat",
        "max_tokens": 5000,
        "name": "GPT-5.2",
    },
    "claude": {
        "id": "anthropic/claude-opus-4.5",
        "max_tokens": 7000,
        "name": "Claude Opus 4.5",
    },
    "gemini": {
        "id": "google/gemini-3-pro-preview",
        "max_tokens": 6000,
        "name": "Gemini 3 Pro",
    },
}

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPTS_PHASE_1 = [
    "1_narrative_mechanics",
    "2_character_functions",
    "3_thematic_decoding",
    "4_visual_symbolic",
    "5_ideological_reading",
]

# Paths relative to script location
BASE_DIR = Path(__file__).parent
DOSSIER_PATH = BASE_DIR / "prompts" / "SEASON_1_DOSSIER.md"
PROMPTS_DIR = BASE_DIR / "prompts" / "phase_1_decoding"
RESULTS_DIR = BASE_DIR / "results" / "phase_1_decoding"
SYNTHESIS_DIR = BASE_DIR / "results" / "synthesis"
GENERATION_DIR = BASE_DIR / "results" / "phase_2_generation"
REWRITE_PROMPT_PATH = BASE_DIR / "prompts" / "rewrite_brief_prompt.md"
REWRITE_OUTPUT_DIR = BASE_DIR / "results" / "synthesis" / "rewritten"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ============================================================================
# TOKEN ESTIMATION
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Rule of thumb: ~4 characters per token for English text.
    More accurate: ~0.75 words per token, or ~1.3 tokens per word.
    """
    # Method 1: Character-based (simple)
    char_estimate = len(text) // 4

    # Method 2: Word-based (slightly more accurate)
    words = len(text.split())
    word_estimate = int(words * 1.3)

    # Return average
    return (char_estimate + word_estimate) // 2


def show_token_estimates(dossier: str, prompts: dict):
    """Display token estimates for context and prompts"""
    print("\n" + "─" * 60)
    print("TOKEN ESTIMATES")
    print("─" * 60)

    dossier_tokens = estimate_tokens(dossier)
    print(f"Season 1 Dossier: ~{dossier_tokens:,} tokens ({len(dossier):,} chars)")

    print("\nPrompts:")
    total_prompt_tokens = 0
    for name, content in prompts.items():
        tokens = estimate_tokens(content)
        total_prompt_tokens += tokens
        print(f"  {name}: ~{tokens:,} tokens")

    print(f"\nPer API call (dossier + 1 prompt): ~{dossier_tokens + (total_prompt_tokens // len(prompts)):,} tokens")
    print(f"Total for all 5 prompts × 3 models: ~{(dossier_tokens * 15) + (total_prompt_tokens * 3):,} input tokens")
    print("─" * 60 + "\n")


# ============================================================================
# API FUNCTIONS
# ============================================================================

def load_env() -> str:
    """Load API key from .env file"""
    env_locations = [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
    ]

    for env_path in env_locations:
        if env_path.exists():
            load_dotenv(env_path)
            break

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("ERROR: OPENROUTER_API_KEY not found")
        print(f"Searched in: {[str(p) for p in env_locations]}")
        print("\nCreate .env file with:")
        print("  OPENROUTER_API_KEY=your_key_here")
        sys.exit(1)
    return api_key


def load_file(path: Path) -> str:
    """Load file contents with error handling"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read {path}: {e}")
        sys.exit(1)


def extract_prompt_text(prompt_content: str) -> str:
    """Extract just the prompt text from the prompt file (inside ``` blocks)"""
    match = re.search(r'```\n(.*?)\n```', prompt_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    if "## Prompt" in prompt_content:
        return prompt_content.split("## Prompt")[1].strip()
    return prompt_content


# Create a session for connection pooling
session = requests.Session()


def call_openrouter(
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    retry_count: int = 0,
) -> Tuple[dict, float]:
    """
    Send request to OpenRouter API with retry logic.
    Returns (response_dict, elapsed_time)
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/pluribus-experiment",
        "X-Title": "Pluribus Decoding Experiment",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    start_time = time.time()

    try:
        response = session.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,  # Use json= instead of data=json.dumps() for efficiency
            timeout=180,
        )
        elapsed = time.time() - start_time

        # Check for HTTP errors
        if response.status_code != 200:
            error_detail = ""
            try:
                error_json = response.json()
                if "error" in error_json:
                    error_detail = error_json["error"]
                    if isinstance(error_detail, dict):
                        error_detail = error_detail.get("message", str(error_detail))
            except:
                error_detail = response.text[:200]

            # Retry on rate limit or server errors
            if response.status_code in [429, 500, 502, 503, 504] and retry_count < MAX_RETRIES:
                print(f"\n    [!] HTTP {response.status_code}, retrying in {RETRY_DELAY}s... ({retry_count + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return call_openrouter(api_key, model, prompt, temperature, max_tokens, retry_count + 1)

            return {"error": f"HTTP {response.status_code}: {error_detail}"}, elapsed

        return response.json(), elapsed

    except requests.exceptions.Timeout:
        if retry_count < MAX_RETRIES:
            print(f"\n    [!] Timeout, retrying in {RETRY_DELAY}s... ({retry_count + 1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            return call_openrouter(api_key, model, prompt, temperature, max_tokens, retry_count + 1)
        return {"error": "Request timed out after 180s (3 retries)"}, time.time() - start_time

    except requests.exceptions.ConnectionError as e:
        if retry_count < MAX_RETRIES:
            print(f"\n    [!] Connection error, retrying in {RETRY_DELAY}s... ({retry_count + 1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            return call_openrouter(api_key, model, prompt, temperature, max_tokens, retry_count + 1)
        return {"error": f"Connection failed: {e}"}, time.time() - start_time

    except Exception as e:
        return {"error": f"Unexpected error: {type(e).__name__}: {e}"}, time.time() - start_time


def extract_response(api_response: dict) -> Tuple[str, Optional[dict], Optional[str]]:
    """
    Extract text, usage, and error from API response.
    Returns (text, usage_dict, error_message)
    """
    if "error" in api_response:
        error_msg = api_response["error"]
        if isinstance(error_msg, dict):
            error_msg = error_msg.get("message", str(error_msg))
        return "", None, str(error_msg)

    try:
        choice = api_response["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # Handle various response formats
        if not content and "reasoning" in message:
            content = message["reasoning"]
        if not content and "parts" in message:
            parts = message["parts"]
            if isinstance(parts, list) and len(parts) > 0:
                content = parts[0].get("text", "")
        if not content and "text" in choice:
            content = choice["text"]

        usage = api_response.get("usage", None)

        if not content:
            return "", usage, f"Empty response (structure: {list(message.keys())})"

        return content, usage, None

    except (KeyError, IndexError) as e:
        return "", None, f"Parse error: {e}"


# ============================================================================
# PHASE 1: DECODING
# ============================================================================

def save_decoding_result(
    prompt_name: str,
    model_name: str,
    response: str,
    usage: Optional[dict],
    elapsed: float,
    output_dir: Path,
) -> Path:
    """Save a single decoding result"""
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{prompt_name}_{model_name}.md"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {prompt_name.replace('_', ' ').title()}\n\n")
        f.write(f"**Model:** {model_name}\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Response time:** {elapsed:.1f}s\n\n")
        f.write("---\n\n")
        f.write(response)
        if usage:
            f.write(f"\n\n---\n\n*Tokens: prompt={usage.get('prompt_tokens', '?')}, ")
            f.write(f"completion={usage.get('completion_tokens', '?')}, ")
            f.write(f"total={usage.get('total_tokens', '?')}*")

    return output_path


def run_phase_1_decoding(temperature: float = 0.7):
    """Run Phase 1: Decode Season 1 through all lenses"""
    api_key = load_env()

    # Load dossier
    print(f"\nLoading dossier: {DOSSIER_PATH}")
    dossier = load_file(DOSSIER_PATH)

    # Load all prompts
    prompts = {}
    for prompt_name in PROMPTS_PHASE_1:
        prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
        if prompt_path.exists():
            content = load_file(prompt_path)
            prompts[prompt_name] = extract_prompt_text(content)
        else:
            print(f"WARNING: Prompt not found: {prompt_path}")

    # Show token estimates
    show_token_estimates(dossier, prompts)

    print("=" * 60)
    print("PHASE 1: DECODING")
    print("=" * 60)
    print(f"Dossier: {len(dossier):,} characters")
    print(f"Prompts: {len(prompts)}")
    print(f"Models: {len(MODELS)}")
    print(f"Total API calls: {len(prompts)} prompts × {len(MODELS)} models = {len(prompts) * len(MODELS)}")
    print(f"Temperature: {temperature}")
    print("=" * 60)

    results_saved = []
    errors = []

    for model_key, model_config in MODELS.items():
        model_id = model_config["id"]
        model_max_tokens = model_config["max_tokens"]
        model_name = model_config["name"]

        print(f"\n{'━' * 60}")
        print(f"MODEL: {model_name}")
        print(f"ID: {model_id}")
        print(f"Max tokens: {model_max_tokens:,}")
        print(f"{'━' * 60}")

        # Always ask for confirmation
        user_input = input(f"\nRun {model_name}? [Y/n/quit]: ").strip().lower()
        if user_input == 'quit' or user_input == 'q':
            print("\nStopping. Results saved so far:")
            for r in results_saved:
                print(f"  ✓ {r.name}")
            if errors:
                print("\nErrors encountered:")
                for e in errors:
                    print(f"  ✗ {e}")
            return results_saved
        if user_input == 'n':
            print(f"Skipping {model_name}")
            continue

        # Run all prompts for this model
        model_start = time.time()

        for i, (prompt_name, prompt_text) in enumerate(prompts.items(), 1):
            # Build full prompt
            full_prompt = f"""Here is the Season 1 Dossier for Pluribus:

{dossier}

---

Now, please complete the following analysis task:

{prompt_text}"""

            input_tokens = estimate_tokens(full_prompt)
            print(f"\n  [{i}/{len(prompts)}] {prompt_name}")
            print(f"      Input: ~{input_tokens:,} tokens")
            print(f"      Sending to {model_key}...", end="", flush=True)

            response, elapsed = call_openrouter(
                api_key=api_key,
                model=model_id,
                prompt=full_prompt,
                temperature=temperature,
                max_tokens=model_max_tokens,
            )

            text, usage, error = extract_response(response)

            if error:
                print(f" ERROR ({elapsed:.1f}s)")
                print(f"      ✗ {error}")
                errors.append(f"{prompt_name}_{model_key}: {error}")
                continue

            # Success
            output_tokens = usage.get('completion_tokens', '?') if usage else '?'
            print(f" OK ({elapsed:.1f}s, {output_tokens} tokens)")

            # Save immediately
            saved_path = save_decoding_result(
                prompt_name=prompt_name,
                model_name=model_key,
                response=text,
                usage=usage,
                elapsed=elapsed,
                output_dir=RESULTS_DIR,
            )
            results_saved.append(saved_path)
            print(f"      ✓ Saved: {saved_path.name}")

        model_elapsed = time.time() - model_start
        print(f"\n  {model_name} complete in {model_elapsed:.1f}s")

    # Final summary
    print("\n" + "=" * 60)
    print("PHASE 1 COMPLETE")
    print("=" * 60)
    print(f"\nSaved {len(results_saved)} files to: {RESULTS_DIR}")

    if errors:
        print(f"\n⚠ {len(errors)} errors occurred:")
        for e in errors:
            print(f"  ✗ {e}")

    print("\nNext steps:")
    print("1. Review the decoding reports")
    print("2. Select the best analyses for synthesis")
    print("3. Create: results/synthesis/unified_brief.md")
    print("4. Create: prompts/phase_2_generation/generation_prompt.md")
    print("5. Run: python pluribus_decode.py --phase 2")

    return results_saved


# ============================================================================
# PHASE 2: GENERATION
# ============================================================================

def run_phase_2_generation(temperature: float = 0.8):
    """Run Phase 2: Generate Season 2 pitches from unified brief"""
    api_key = load_env()

    # Check for unified brief
    brief_path = SYNTHESIS_DIR / "unified_brief.md"
    if not brief_path.exists():
        print(f"\nERROR: Unified brief not found at {brief_path}")
        print("\nComplete Phase 1 synthesis first:")
        print("1. Review decoding reports in results/phase_1_decoding/")
        print("2. Create: results/synthesis/unified_brief.md")
        sys.exit(1)

    brief = load_file(brief_path)

    # Check for generation prompt
    gen_prompt_path = BASE_DIR / "prompts" / "phase_2_generation" / "generation_prompt.md"
    if not gen_prompt_path.exists():
        print(f"\nERROR: Generation prompt not found at {gen_prompt_path}")
        print("Create the generation prompt first.")
        sys.exit(1)

    gen_prompt_content = load_file(gen_prompt_path)
    gen_prompt_text = extract_prompt_text(gen_prompt_content)

    # Token estimate
    full_prompt = f"""Here is the decoded analysis of Pluribus Season 1:

{brief}

---

Now, based on this decoded understanding, please complete the following:

{gen_prompt_text}"""

    input_tokens = estimate_tokens(full_prompt)

    print("\n" + "=" * 60)
    print("PHASE 2: GENERATION")
    print("=" * 60)
    print(f"Unified brief: {len(brief):,} characters")
    print(f"Input tokens: ~{input_tokens:,}")
    print(f"Models: {len(MODELS)}")
    print(f"Temperature: {temperature}")
    print("=" * 60)

    results_saved = []
    errors = []

    for model_key, model_config in MODELS.items():
        model_id = model_config["id"]
        model_max_tokens = model_config["max_tokens"]
        model_name = model_config["name"]

        user_input = input(f"\nRun {model_name}? [Y/n/quit]: ").strip().lower()
        if user_input == 'quit' or user_input == 'q':
            break
        if user_input == 'n':
            continue

        print(f"\nSending to {model_name}...", end="", flush=True)

        response, elapsed = call_openrouter(
            api_key=api_key,
            model=model_id,
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=model_max_tokens,
        )

        text, usage, error = extract_response(response)

        if error:
            print(f" ERROR ({elapsed:.1f}s)")
            print(f"  ✗ {error}")
            errors.append(f"{model_key}: {error}")
            continue

        output_tokens = usage.get('completion_tokens', '?') if usage else '?'
        print(f" OK ({elapsed:.1f}s, {output_tokens} tokens)")

        # Save result
        GENERATION_DIR.mkdir(parents=True, exist_ok=True)
        output_path = GENERATION_DIR / f"pitch_{model_key}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Season 2 Pitch - {model_name}\n\n")
            f.write(f"**Model:** {model_id}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Response time:** {elapsed:.1f}s\n\n")
            f.write("---\n\n")
            f.write(text)
            if usage:
                f.write(f"\n\n---\n\n*Tokens: {usage.get('total_tokens', '?')}*")

        results_saved.append(output_path)
        print(f"  ✓ Saved: {output_path}")

    print("\n" + "=" * 60)
    print("PHASE 2 COMPLETE")
    print("=" * 60)
    print(f"\nSaved {len(results_saved)} pitches to: {GENERATION_DIR}")

    if errors:
        print(f"\n⚠ {len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")

    return results_saved


# ============================================================================
# REWRITE: TRANSFORM UNIFIED BRIEF
# ============================================================================

def run_brief_rewrite(temperature: float = 0.7):
    """Curate best quotes from the BRIEF analysis files"""
    api_key = load_env()

    # Find all BRIEF files
    brief_files = sorted(RESULTS_DIR.glob("*_BRIEF.md"))
    if not brief_files:
        print(f"\nERROR: No *_BRIEF.md files found in {RESULTS_DIR}")
        print("Run Phase 1 and select your best analyses first.")
        sys.exit(1)

    # Load and concatenate BRIEF files with clear attribution
    source_sections = []
    for brief_file in brief_files:
        content = load_file(brief_file)
        # Extract model name from filename (e.g., "1_narrative_mechanics_gpt_BRIEF.md" -> "GPT")
        parts = brief_file.stem.replace("_BRIEF", "").split("_")
        model_name = parts[-1].upper()  # Last part before _BRIEF
        lens_name = " ".join(parts[:-1]).replace("_", " ").title()

        section = f"""
================================================================================
SOURCE: {brief_file.name}
MODEL: {model_name}
LENS: {lens_name}
================================================================================

{content}
"""
        source_sections.append(section)

    combined_sources = "\n".join(source_sections)

    # Check for rewrite prompt
    if not REWRITE_PROMPT_PATH.exists():
        print(f"\nERROR: Rewrite prompt not found at {REWRITE_PROMPT_PATH}")
        print("Create the rewrite prompt first.")
        sys.exit(1)

    rewrite_prompt = load_file(REWRITE_PROMPT_PATH)

    # Build full prompt
    full_prompt = f"""{rewrite_prompt}

---

SOURCE DOCUMENTS (5 analyses, each labeled with MODEL):

{combined_sources}"""

    input_tokens = estimate_tokens(full_prompt)

    print("\n" + "=" * 60)
    print("CURATE: SELECT BEST QUOTES FROM BRIEF FILES")
    print("=" * 60)
    print(f"Source files: {len(brief_files)}")
    for bf in brief_files:
        parts = bf.stem.replace("_BRIEF", "").split("_")
        model = parts[-1].upper()
        print(f"  - {bf.name} ({model})")
    print(f"Combined: {len(combined_sources):,} characters")
    print(f"Total input: ~{input_tokens:,} tokens")
    print(f"Temperature: {temperature}")
    print("=" * 60)
    print("\nThis will send to ONE model at a time.")
    print("Review each output before deciding to run another model.")

    results_saved = []
    errors = []

    for model_key, model_config in MODELS.items():
        model_id = model_config["id"]
        model_max_tokens = model_config["max_tokens"]
        model_name = model_config["name"]

        print(f"\n{'─' * 60}")
        user_input = input(f"Run {model_name}? [Y/n/quit]: ").strip().lower()

        if user_input == 'quit' or user_input == 'q':
            print("\nStopping.")
            break
        if user_input == 'n':
            print(f"Skipping {model_name}")
            continue

        print(f"Sending to {model_name}...", end="", flush=True)

        response, elapsed = call_openrouter(
            api_key=api_key,
            model=model_id,
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=model_max_tokens,
        )

        text, usage, error = extract_response(response)

        if error:
            print(f" ERROR ({elapsed:.1f}s)")
            print(f"  ✗ {error}")
            errors.append(f"{model_key}: {error}")
            continue

        output_tokens = usage.get('completion_tokens', '?') if usage else '?'
        print(f" OK ({elapsed:.1f}s, {output_tokens} tokens)")

        # Save result
        REWRITE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REWRITE_OUTPUT_DIR / f"brief_{model_key}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Unified Brief — Rewritten by {model_name}\n\n")
            f.write(f"**Model:** {model_id}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Response time:** {elapsed:.1f}s\n\n")
            f.write("---\n\n")
            f.write(text)
            if usage:
                f.write(f"\n\n---\n\n*Tokens: prompt={usage.get('prompt_tokens', '?')}, ")
                f.write(f"completion={usage.get('completion_tokens', '?')}, ")
                f.write(f"total={usage.get('total_tokens', '?')}*")

        results_saved.append(output_path)
        print(f"  ✓ Saved: {output_path}")

        # Show preview
        preview_lines = text.split('\n')[:10]
        print(f"\n  Preview (first 10 lines):")
        for line in preview_lines:
            print(f"    {line[:80]}")
        if len(text.split('\n')) > 10:
            print(f"    ... ({len(text.split(chr(10)))} total lines)")

    # Summary
    print("\n" + "=" * 60)
    print("REWRITE COMPLETE")
    print("=" * 60)

    if results_saved:
        print(f"\nSaved {len(results_saved)} rewritten brief(s) to: {REWRITE_OUTPUT_DIR}")
        for path in results_saved:
            print(f"  ✓ {path.name}")

    if errors:
        print(f"\n⚠ {len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")

    return results_saved


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Pluribus Multi-Phase Experiment: Decode, Rewrite, Generate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  Phase 1: Decode Season 1 through 5 analytical lenses
           → You confirm each model before it runs
           → Results saved immediately after each prompt

  Synthesis: YOU review reports and create unified brief

  Rewrite:  Transform unified brief into curator's essay
           → One model at a time, review before continuing

  Phase 2: Generate Season 2 pitches from decoded understanding

Examples:
  ./pluribus_decode.py                    # Run Phase 1 (decoding)
  ./pluribus_decode.py --rewrite          # Rewrite unified brief
  ./pluribus_decode.py --phase 2          # Run Phase 2 (generation)
  ./pluribus_decode.py --temperature 0.8  # Custom temperature
        """,
    )

    parser.add_argument(
        "--phase",
        "-p",
        type=int,
        choices=[1, 2],
        default=1,
        help="Which phase to run (1=decoding, 2=generation)",
    )

    parser.add_argument(
        "--rewrite",
        "-r",
        action="store_true",
        help="Rewrite the unified brief into a curator's essay",
    )

    parser.add_argument(
        "--temperature",
        "-t",
        type=float,
        default=None,
        help="Model temperature (default: 0.7 for decoding/rewrite, 0.8 for generation)",
    )

    args = parser.parse_args()

    if args.rewrite:
        temp = args.temperature if args.temperature is not None else 0.7
        run_brief_rewrite(temperature=temp)
    elif args.phase == 1:
        temp = args.temperature if args.temperature is not None else 0.7
        run_phase_1_decoding(temperature=temp)
    else:
        temp = args.temperature if args.temperature is not None else 0.8
        run_phase_2_generation(temperature=temp)


if __name__ == "__main__":
    main()
