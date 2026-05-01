import json
import os
import requests
import subprocess
import threading
import time
import itertools
import sys
import ollama

MODEL = os.environ.get("SOFTMOTHER_OLLAMA_MODEL", "qwen3.5:397b-cloud")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_EMBED_MODEL = os.environ.get("SOFTMOTHER_OLLAMA_EMBED_MODEL", "llama3:8b")
OPENROUTER_EMBED_MODEL = os.environ.get(
    "OPENROUTER_EMBED_MODEL",
    "openai/text-embedding-3-small",
)
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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",
)
LLM_PROVIDER_ENV = "SOFTMOTHER_LLM_PROVIDER"
ACTIVE_LLM_PROVIDER = None
FILE_CONTEXT_JSON = "fileContent.json"
PLAN_OUTPUT_JSON = "plan.json"
ACCENT = "\033[38;2;50;205;194m"
BG = "\033[48;2;11;16;32m"
RESET = "\033[0m"
THINKING_FRAMES = (
    "✚",
    "✢",
    "✣",
    "✤",
    "✥",
    "✦",
    "✧",
    "✜",
    "✛",
    "✖",
    "✚",
)


def _prepare_terminal_output():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _clear_status_line(label):
    width = max(40, len(label) + 12)
    sys.stdout.write("\r" + (" " * width) + "\r")
    sys.stdout.flush()


def _thinking_loop(label, stop_event):
    frames = itertools.cycle(THINKING_FRAMES)
    while not stop_event.is_set():
        symbol = next(frames)
        sys.stdout.write(f"\r{BG}{ACCENT}{label} {symbol}{RESET}")
        sys.stdout.flush()
        if stop_event.wait(0.11):
            break
    _clear_status_line(label)


def run_with_thinking(label, func, *args, **kwargs):
    _prepare_terminal_output()

    if not getattr(sys.stdout, "isatty", lambda: False)():
        return func(*args, **kwargs)

    stop_event = threading.Event()
    animation = threading.Thread(
        target=_thinking_loop,
        args=(label, stop_event),
        daemon=True,
    )
    animation.start()

    try:
        return func(*args, **kwargs)
    finally:
        stop_event.set()
        animation.join(timeout=1.0)
        _clear_status_line(label)


def normalize_llm_provider(provider):
    """Normalize accepted backend names to 'openrouter' or 'ollama'."""
    normalized = str(provider or "").strip().lower()
    aliases = {
        "1": "openrouter",
        "openrouter": "openrouter",
        "open route": "openrouter",
        "openroute": "openrouter",
        "cloud": "openrouter",
        "2": "ollama",
        "ollama": "ollama",
        "local": "ollama",
    }
    return aliases.get(normalized)


def set_llm_provider(provider):
    """Persist the selected LLM backend for the current process."""
    global ACTIVE_LLM_PROVIDER

    normalized = normalize_llm_provider(provider)
    if normalized not in {"openrouter", "ollama"}:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    ACTIVE_LLM_PROVIDER = normalized
    os.environ[LLM_PROVIDER_ENV] = normalized
    return normalized


def choose_llm_provider(preferred=None, prompt_user=True):
    """Select the LLM backend once, prompting the user when needed."""
    global ACTIVE_LLM_PROVIDER

    if ACTIVE_LLM_PROVIDER:
        return ACTIVE_LLM_PROVIDER

    preset = normalize_llm_provider(preferred) or normalize_llm_provider(
        os.environ.get(LLM_PROVIDER_ENV)
    )
    if preset:
        return set_llm_provider(preset)

    if not prompt_user or not getattr(sys.stdin, "isatty", lambda: False)():
        return set_llm_provider("ollama")

    print("\nChoose the LLM backend:")
    print("1. OpenRouter (cloud)")
    print("2. Ollama (local)")

    while True:
        choice = input("Select backend [1/2]: ").strip()
        normalized = normalize_llm_provider(choice)
        if normalized:
            return set_llm_provider(normalized)
        print("Please choose 1 for OpenRouter or 2 for Ollama.")


def get_llm_provider():
    """Return the active LLM backend, prompting once if necessary."""
    return choose_llm_provider()


def resolve_chat_model(requested_model=None):
    """Map chat prompts to the active backend's model."""
    if get_llm_provider() == "openrouter":
        return OPENROUTER_MODEL
    return requested_model or MODEL


def resolve_embedding_model(requested_model=None):
    """Map embedding requests to the active backend's model."""
    if get_llm_provider() == "openrouter":
        return requested_model or OPENROUTER_EMBED_MODEL
    return requested_model or OLLAMA_EMBED_MODEL


def _extract_openrouter_delta(payload):
    """Extract streamed token text from an OpenRouter SSE chunk."""
    choices = payload.get("choices") or []
    if not choices:
        return ""

    choice = choices[0]
    delta = choice.get("delta") or {}
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "".join(parts)
        if content:
            return str(content)

    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "".join(parts)
    if content:
        return str(content)

    return ""


def openrouter_chat(model=None, messages=None, **kwargs):
    """Call OpenRouter's chat completions API and return an Ollama-like shape."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OpenRouter is selected but OPENROUTER_API_KEY is not configured."
        )

    payload = {
        "model": resolve_chat_model(model),
        "messages": messages or [],
        "stream": True,
    }

    for key, value in kwargs.items():
        if key == "stream" or value is None:
            continue
        payload[key] = value

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        stream=True,
        timeout=300,
    )
    response.raise_for_status()

    reply = ""
    for chunk in response.iter_lines():
        if not chunk:
            continue

        data = chunk.decode("utf-8")
        if not data.startswith("data: "):
            continue

        body = data[6:]
        if body.strip() == "[DONE]":
            break

        try:
            payload_chunk = json.loads(body)
        except json.JSONDecodeError:
            continue

        reply += _extract_openrouter_delta(payload_chunk)

    return {"message": {"content": reply}}


def _stream_openrouter_chat(model=None, messages=None, **kwargs):
    """Yield streamed text chunks from OpenRouter chat completions."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OpenRouter is selected but OPENROUTER_API_KEY is not configured."
        )

    payload = {
        "model": resolve_chat_model(model),
        "messages": messages or [],
        "stream": True,
    }

    for key, value in kwargs.items():
        if key == "stream" or value is None:
            continue
        payload[key] = value

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        stream=True,
        timeout=300,
    )
    response.raise_for_status()

    for chunk in response.iter_lines():
        if not chunk:
            continue

        data = chunk.decode("utf-8")
        if not data.startswith("data: "):
            continue

        body = data[6:]
        if body.strip() == "[DONE]":
            break

        try:
            payload_chunk = json.loads(body)
        except json.JSONDecodeError:
            continue

        text = _extract_openrouter_delta(payload_chunk)
        if text:
            yield text


def _extract_ollama_stream_chunk(chunk):
    """Extract streamed token text from an Ollama chat chunk."""
    if isinstance(chunk, dict):
        message = chunk.get("message") or {}
        return str(message.get("content") or "")

    message = getattr(chunk, "message", None)
    if message is not None:
        content = getattr(message, "content", "")
        if content:
            return str(content)

    return ""


def llm_chat(**kwargs):
    """Dispatch chat prompts to the selected backend."""
    if get_llm_provider() == "openrouter":
        return openrouter_chat(**kwargs)
    kwargs["model"] = resolve_chat_model(kwargs.get("model"))
    return ollama.chat(**kwargs)


def ollama_chat_with_status(label, **kwargs):
    return run_with_thinking(label, llm_chat, **kwargs)


def stream_llm_chat(**kwargs):
    """Yield streamed text chunks from the selected chat backend."""
    if get_llm_provider() == "openrouter":
        yield from _stream_openrouter_chat(**kwargs)
        return

    kwargs["model"] = resolve_chat_model(kwargs.get("model"))
    kwargs["stream"] = True
    for chunk in ollama.chat(**kwargs):
        text = _extract_ollama_stream_chunk(chunk)
        if text:
            yield text


def openrouter_embed(model=None, input=None, **kwargs):
    """Call OpenRouter's embeddings API and return an Ollama-like shape."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OpenRouter is selected but OPENROUTER_API_KEY is not configured."
        )

    payload = {
        "model": resolve_embedding_model(model),
        "input": input,
        "encoding_format": "float",
    }

    for key, value in kwargs.items():
        if value is None:
            continue
        payload[key] = value

    response = requests.post(
        OPENROUTER_EMBED_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    response.raise_for_status()

    data = response.json()
    embeddings = [
        item["embedding"]
        for item in data.get("data", [])
        if isinstance(item, dict) and "embedding" in item
    ]
    return {"embeddings": embeddings, "model": data.get("model")}


def llm_embed(**kwargs):
    """Dispatch embedding requests to the selected backend."""
    kwargs["model"] = resolve_embedding_model(kwargs.get("model"))
    if get_llm_provider() == "openrouter":
        return openrouter_embed(**kwargs)
    return ollama.embed(**kwargs)


def embed_with_status(label, **kwargs):
    return run_with_thinking(label, llm_embed, **kwargs)


def ollama_embed_with_status(label, **kwargs):
    return embed_with_status(label, **kwargs)



def load_file_context(json_path=FILE_CONTEXT_JSON, threshold=0.5):
    """Load file context and prioritize flagged files if available.

    Args:
        json_path: Path to the fileContent.json
        threshold: Minimum flag score (0.0-1.0) to include (default 0.5)
    """
    if not os.path.exists(json_path) or os.path.getsize(json_path) == 0:
        return []

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Filter by priority score (0.0-1.0 scale)
    flagged_files = [
        item for item in data
        if float(item.get("flag", 0.0)) >= threshold
    ]
    # Sort by priority descending
    flagged_files.sort(key=lambda x: float(x.get("flag", 0.0)), reverse=True)

    return flagged_files or data


def build_context_for_prompt(file_context):
    """Convert file context into a compact prompt-friendly summary."""
    if not file_context:
        return "No file context available."

    context_blocks = []
    for item in file_context:
        context_blocks.append(
            {
                "name": item.get("name", ""),
                "notes": item.get("notes", ""),
                "flag": int(item.get("flag", 0)),
                "content_preview": item.get("content", "")[:3000],
            }
        )

    return json.dumps(context_blocks, indent=2, ensure_ascii=False)


def prioritize_flagged_files(file_context, threshold=0.5):
    """Prefer flagged files when they exist, sorted by priority.

    Args:
        file_context: List of file entries with flag scores (0.0-1.0)
        threshold: Minimum score to be considered flagged (default 0.5)
    """
    flagged_files = [
        item for item in file_context
        if float(item.get("flag", 0.0)) >= threshold
    ]
    # Sort by priority descending
    flagged_files.sort(key=lambda x: float(x.get("flag", 0.0)), reverse=True)
    return flagged_files or file_context


def extract_json_text(raw_text):
    """Extract JSON content even if the model wraps it in markdown fences."""
    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start_index = cleaned.find("[")
    end_index = cleaned.rfind("]")
    if start_index != -1 and end_index != -1 and end_index > start_index:
        return cleaned[start_index:end_index + 1]

    start_index = cleaned.find("{")
    end_index = cleaned.rfind("}")
    if start_index != -1 and end_index != -1 and end_index > start_index:
        return cleaned[start_index:end_index + 1]

    return cleaned


def normalize_plan(plan_data):
    """Normalize model output into a list of {step, tools} objects."""
    if isinstance(plan_data, dict):
        if "plan" in plan_data and isinstance(plan_data["plan"], list):
            plan_data = plan_data["plan"]
        else:
            plan_data = [plan_data]

    normalized = []
    for item in plan_data:
        if not isinstance(item, dict):
            continue

        step = str(item.get("step", "")).strip()
        tools = item.get("tools", [])

        if isinstance(tools, str):
            tools = [tools]
        elif not isinstance(tools, list):
            tools = []

        tools = [str(tool).strip() for tool in tools if str(tool).strip()]

        if step:
            normalized.append(
                {
                    "step": step,
                    "tools": tools,
                }
            )

    return normalized


def planner(task, file_entry):
    """Ask Ollama for a detailed JSON plan with tools for each step for a specific file.

    Args:
        task: The overall task description
        file_entry: Single file dict with name, notes, content, flag
    """
    content_preview = file_entry.get("content", "")[:6000]
    file_name = file_entry.get("name", "unknown")
    file_notes = file_entry.get("notes", "")

    response = ollama_chat_with_status(
        "Planning",
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a planner for a coding assistant agent. "
                    "Return only valid JSON. "
                    "The JSON must be an array. "
                    "Each array item must have exactly these keys: "
                    '"step" and "tools". '
                    '"step" must be a detailed string. '
                    '"tools" must be an array of strings listing the tools needed to complete that step. '
                    "Do not include markdown fences or explanations outside JSON. "
                    "STRICTLY adhere to the user's task - do not add features or changes "
                    "that were not explicitly requested."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User's Task (STRICT CONSTRAINT - only implement what is asked):\n{task}\n\n"
                    f"File: {file_name}\n"
                    f"Summary: {file_notes}\n\n"
                    f"File content:\n{content_preview}\n\n"
                    "Create a detailed step-by-step implementation plan for THIS FILE ONLY. "
                    "Include ONLY steps that directly implement the user's task. "
                    "Do not add refactoring, optimizations, or features not requested. "
                    "For each step, include the tools that can be used to write or modify the code."
                ),
            },
        ],
    )

    return response["message"]["content"]


def refinedTask(task, file_entry):
    """Return a plain-English sentence describing what will be fixed in a specific file.

    The refined task is strictly derived from the user's original task - no additions.

    Args:
        task: The overall task description (user's original input)
        file_entry: Single file dict with name, notes, content, flag
    """
    content_preview = file_entry.get("content", "")[:6000]
    file_name = file_entry.get("name", "unknown")
    file_notes = file_entry.get("notes", "")

    response = ollama_chat_with_status(
        "Refining task",
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze coding tasks and file content. "
                    "Return one plain-English sentence describing what will be done in this specific file. "
                    "STRICTLY base your response on the user's task - do not add features or changes "
                    "that were not requested. Be file-specific and detailed. "
                    "Do not use markdown, bullet points, or JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User's Task (STRICT CONSTRAINT - only do what is asked):\n{task}\n\n"
                    f"File: {file_name}\n"
                    f"Summary: {file_notes}\n\n"
                    f"File content:\n{content_preview}\n\n"
                    "Explain in one clear English sentence what specifically will be done in this file "
                    "to fulfill the user's task. Only include changes directly required by the task."
                ),
            },
        ],
    )

    return response["message"]["content"].strip()


def validate_plan_against_task(task_given, refined_task, step):
    """Validate that a plan step is directly derived from the user's task.

    Returns a relevance score (0.0 to 1.0) indicating how well the step
    aligns with the user's original task.

    Args:
        task_given: The user's original task
        refined_task: The file-specific refined task
        step: A specific step from the plan

    Returns:
        float: 1.0 = step is essential to the task, 0.0 = step is unrelated
    """
    if not task_given.strip():
        return 0.0

    try:
        response = ollama_chat_with_status(
            "Validating",
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a validator that checks if a proposed code change step "
                        "is directly derived from the user's original task. "
                        "Return a float between 0.0 and 1.0: "
                        "1.0 = step is essential and directly implements the task, "
                        "0.5 = step is tangentially related but not core, "
                        "0.0 = step is unrelated or goes beyond what was asked. "
                        "Be strict - only validate what the user actually requested. "
                        "Return ONLY the number."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User's Original Task:\n{task_given}\n\n"
                        f"File's Refined Task:\n{refined_task}\n\n"
                        f"Proposed Step:\n{step}\n\n"
                        "Is this step strictly necessary to implement the user's task? "
                        "Return a relevance score (0.0 to 1.0)."
                    ),
                },
            ],
        )
        score_str = str(response["message"]["content"]).strip()
        score = float(score_str)
        return max(0.0, min(1.0, score))
    except (ValueError, TypeError, Exception) as error:
        print(f"Validation failed: {error}")
        return 0.0


def save_plan(files_plan, output_path=PLAN_OUTPUT_JSON):
    """Save per-file plan data to JSON.

    Args:
        files_plan: List of dicts, each containing file_name, refined_task, and plan
    """
    payload = {
        "files": files_plan,
    }
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def print_plan_beautifully(files_plan, task):
    """Print the per-file plan in a readable terminal format."""
    print("\n" + "=" * 90)
    print("DETAILED EXECUTION PLAN (PER FILE)")
    print("=" * 90)
    print(f"Task: {task}")
    print("=" * 90)

    if not files_plan:
        print("No valid plan was generated.")
        print("=" * 90)
        return

    for file_entry in files_plan:
        file_name = file_entry.get("file_name", "unknown")
        refined_task = file_entry.get("refined_task", "")
        plan = file_entry.get("plan", [])

        print(f"\nFILE: {file_name}")
        print("-" * 90)
        print(f"Refined Task: {refined_task}")
        print("-" * 90)

        for index, item in enumerate(plan, start=1):
            print(f"\n  STEP {index}")
            print("  " + "-" * 50)
            print(f"  {item['step']}")
            print(f"  Tools: {', '.join(item['tools']) if item['tools'] else 'No tools suggested'}")

    print(f"\nPlan saved to: {PLAN_OUTPUT_JSON}")
    print("=" * 90)


def main():
    task = input("Enter the task for the planner: ").strip()
    if not task:
        print("Task cannot be empty.")
        return

    file_context = load_file_context()
    if not file_context:
        print("No file context available.")
        return

    # Process each file individually
    files_plan = []
    for file_entry in file_context:
        file_name = file_entry.get("name", "unknown")
        print(f"Generating plan for: {file_name}")

        file_refined_task = refinedTask(task, file_entry)
        raw_plan = planner(task, file_entry)
        json_text = extract_json_text(raw_plan)

        try:
            parsed_plan = json.loads(json_text)
            normalized_plan = normalize_plan(parsed_plan)
        except json.JSONDecodeError:
            print(f"Planner returned invalid JSON for {file_name}. Using empty plan.")
            normalized_plan = []

        files_plan.append({
            "file_name": file_name,
            "refined_task": file_refined_task,
            "plan": normalized_plan,
        })

    save_plan(files_plan)
    print_plan_beautifully(files_plan, task)

def navigate_to_file(TARGET_FOLDER_PATH, file_name):
    import subprocess

    path = TARGET_FOLDER_PATH + "/" + file_name

    command = f'cd "{path}"; Get-Location'

    result = subprocess.run(
        ["powershell", "-Command", command],
        capture_output=True,
        text=True
    )


def get_file_content_from_chromadb(file_name, db_path=None, collection_name=None):
    """Retrieve file content from ChromaDB by file name.

    Args:
        file_name: Name of the file to retrieve
        db_path: Path to ChromaDB (defaults to CHROMA_DB_PATH from main.py)
        collection_name: Collection name (defaults to COLLECTION_NAME)

    Returns:
        dict with file content and metadata, or None if not found
    """
    import chromadb
    import os

    DEFAULT_DB_ROOT = os.environ.get("LOCALAPPDATA", os.getcwd())
    db_path = db_path or os.path.join(DEFAULT_DB_ROOT, "SoftMother", "chroma_db")
    collection_name = collection_name or "file_contents"

    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(name=collection_name)

        # Query by metadata (file name)
        results = collection.get(
            where={"name": file_name},
            include=["documents", "metadatas"]
        )

        if results["ids"] and len(results["ids"]) > 0:
            return {
                "file_name": file_name,
                "content": results["documents"][0],
                "metadata": results["metadatas"][0] if results["metadatas"] else {},
            }
        else:
            print(f"File '{file_name}' not found in ChromaDB.")
            return None

    except Exception as error:
        print(f"Error retrieving file from ChromaDB: {error}")
        return None

def apply_file_edit(file_path, current_content, step_description):
    """Apply an edit to a file based on the step description.

    Args:
        file_path: Path to the file to edit
        current_content: Current content of the file
        step_description: Description of what change to make
    """
    try:
        response = ollama_chat_with_status(
            "Fixing code",
            model='qwen3.5:397b-cloud',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a code editor. Return ONLY the complete corrected file content. '
                        'Do not include explanations, markdown fences, or any other text. '
                        'Apply the requested fix to the file content.'
                    )
                },
                {
                    'role': 'user',
                    'content': (
                        f'Current file content:\n{current_content}\n\n'
                        f'Required fix: {step_description}\n\n'
                        'Return the complete fixed file content only, nothing else.'
                    )
                }
            ]
        )
        corrected_content = response["message"]["content"].strip()

        # Clean markdown fences if present
        if corrected_content.startswith("```"):
            lines = corrected_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            corrected_content = "\n".join(lines).strip()

        # Write the corrected content to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(corrected_content)

        print(f"    File updated: {file_path}")
        return True

    except Exception as e:
        print(f"    Error applying edit: {e}")
        return False


def implementing_changes(content, step, path):
    """Apply the step's changes to the file.

    Args:
        content: Current file content
        step: Description of the change to make
        path: Full path to the file
    """
    apply_file_edit(path, content, step)

def stream_clean_response(response):
    """
    Streams Ollama response cleanly.
    Ignores blank chunks during thinking phase.
    Shows spinner while model is thinking.
    Returns full final text.
    """

    final_text = ""
    started_output = False
    spinner = itertools.cycle(["⠁", "⠂", "⠄", "⠂"])

    for message in response:
        chunk = message["message"]["content"]

        # If chunk is blank, model is likely thinking
        if not chunk.strip():
            if not started_output:
                sys.stdout.write("\rThinking " + next(spinner))
                sys.stdout.flush()
                time.sleep(0.05)
            continue

        # First visible token arrived
        if not started_output:
            sys.stdout.write("\r" + " " * 30 + "\r")   # clear spinner line
            started_output = True

        print(chunk, end="", flush=True)
        final_text += chunk

    print()
    return final_text

if __name__ == "__main__":
    main()
