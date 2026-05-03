import argparse
import hashlib
import json
import os
import chromadb
from chromadb.utils import embedding_functions
from chatbot import *
from rectification import rectification
from terminalAccess import run_terminal_task

DEFAULT_DB_ROOT = os.environ.get("LOCALAPPDATA", os.getcwd())
CHROMA_DB_PATH = os.path.join(DEFAULT_DB_ROOT, "SoftMother", "chroma_db")

MODEL = "qwen3.5:397b-cloud"
SUMMARY_MODEL = "qwen3.5:397b-cloud"
FLAG_MODEL = "qwen3.5:397b-cloud"
CHAT_EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit"}
CHAT_SYSTEM_PROMPTS = {
    "ollama": (
        "You are KittyClaw's normal conversation assistant running on the Ollama "
        "pipeline with the qwen3.5:397b-cloud model. Reply like a helpful, natural "
        "chatbot. Be conversational, clear, and concise."
    ),
    "openrouter": (
        "You are KittyClaw's normal conversation assistant running on the OpenRouter "
        "pipeline with the openrouter/free model. Reply like a helpful, natural "
        "chatbot. Be conversational, clear, and concise."
    ),
}


def resolve_target_folder(target_folder=None):
    """Return the folder KittyClaw should analyze for the current run."""
    return os.path.abspath(target_folder or os.getcwd())


def classify_user_command(user_input):
    """Route commands by prefix: # terminal, ! coding, plain text chat."""
    text = str(user_input or "").strip()
    if not text:
        return "empty", ""
    if text.startswith("#"):
        return "terminal", text[1:].strip()
    if text.startswith("!"):
        return "coding", text[1:].strip()
    return "chat", text


def get_chat_pipeline_name(provider):
    """Return the human-readable chat pipeline label for the active backend."""
    if provider == "openrouter":
        return "OpenRouter conversation pipeline (openrouter/free)"
    return "Ollama conversation pipeline (qwen3.5:397b-cloud)"


def run_chat_pipeline(message, conversation_history):
    """Reply as a normal chatbot using the selected provider pipeline."""
    provider = get_llm_provider()
    system_prompt = CHAT_SYSTEM_PROMPTS.get(provider, CHAT_SYSTEM_PROMPTS["ollama"])

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": message})

    print(f"KittyClaw : ", end="", flush=True)
    chunks = []
    try:
        for chunk in stream_llm_chat(messages=messages):
            print(chunk, end="", flush=True)
            chunks.append(chunk)
    except RuntimeError as error:
        fallback_message = str(error).strip() or OPENROUTER_UNAVAILABLE_MESSAGE
        print(fallback_message, end="", flush=True)
        chunks = [fallback_message]
    print()
    reply = "".join(chunks).strip()

    conversation_history.append({"role": "user", "content": message})
    conversation_history.append({"role": "assistant", "content": reply})


def run_coding_agent_pipeline(target_folder, task_given):
    """Run the identify + plan + rectify coding workflow."""
    print(f"Target folder: {target_folder}")
    print("Routing task to coding agent.")
    data = save_files_to_json(target_folder, task_given=task_given)
    print_flagged_files(data)
    store_json_data_in_chromadb(data)
    files_plan, _ = generate_and_save_plan(task_given, data)
    print_refined_task(files_plan)
    print(f"Saved {len(files_plan)} file plans to plan.json")
    if files_plan:
        print("\n" + "=" * 80)
        print("STARTING RECTIFICATION PIPELINE")
        print("=" * 80)
        rectification(target_folder, task_given)
    else:
        print("No actionable coding plan was generated.")


def route_user_command(user_input, target_folder, conversation_history):
    """Dispatch a single user input to terminal, coding, or chat pipelines."""
    route, payload = classify_user_command(user_input)

    if route == "empty":
        print("Input cannot be empty.")
        return True

    try:
        if route == "terminal":
            if not payload:
                print("Terminal task cannot be empty after '#'.")
                return True
            print(f"Target folder: {target_folder}")
            print("Routing task to terminal automation.")
            run_terminal_task(payload, target_folder=target_folder)
            return True

        if route == "coding":
            if not payload:
                print("Coding task cannot be empty after '!'.")
                return True
            run_coding_agent_pipeline(target_folder, payload)
            return True

        run_chat_pipeline(payload, conversation_history)
    except RuntimeError as error:
        message = str(error).strip() or "An unexpected error occurred."
        print(message)
    return True


def interactive_router_loop(target_folder, initial_task=None):
    """Keep the router running so plain text behaves like a normal chatbot."""
    conversation_history = []

    if initial_task is not None:
        route_user_command(initial_task, target_folder, conversation_history)
        return

    print("\nMode routing:")
    print("  #task  -> terminal automation")
    print("  !task  -> coding agent pipeline")
    print("  text   -> normal chatbot conversation")
    print("Type exit or quit to leave.\n")

    while True:
        user_input = input("How can i help : ").strip()
        if user_input.lower() in CHAT_EXIT_COMMANDS:
            print("Exiting KittyClaw.")
            break
        route_user_command(user_input, target_folder, conversation_history)


def read_all_files_in_folder(folder_path, task_given=""):
    """Read all files in the specified folder and return their contents."""
    file_contents = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    notes = generate_file_summary(content)
                    file_contents.append(
                        {
                            "name": filename,
                            "notes": notes,
                            "content": content,
                            "flag": generate_file_flag(
                                filename=filename,
                                notes=notes,
                                content=content,
                                task_given=task_given,
                            ),
                        }
                    )
            except Exception as error:
                print(f"Error reading {filename}: {error}")
    return file_contents


def generate_file_summary(content, model_name=SUMMARY_MODEL):
    """Generate a short English summary for a file without blocking ingestion on failure."""
    try:
        response = ollama_chat_with_status(
            "Summarizing",
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You summarize source files in plain English. "
                        "Keep it short and do not quote the code. the file can be any programming language or text. Just give a brief summary of what the file does."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Read this file and give a short English summary of what it does.\n\n"
                        f"{content}"
                    ),
                },
            ],
        )
        return response["message"]["content"].strip()
    except Exception as error:
        print(f"Summary generation failed: {error}")
        return ""


def normalize_flag(raw_flag):
    """Return a priority score between 0 and 1 based on task relevance.

    The model returns a float (0.0 to 1.0) indicating how important the file is
    for implementing the given task. 1.0 = critical, 0.0 = irrelevant.
    """
    try:
        score = float(str(raw_flag).strip())
        return max(0.0, min(1.0, score))
    except (ValueError, TypeError):
        return 0.0


def generate_file_flag(filename, notes, content, task_given, model_name=FLAG_MODEL):
    """Generate a 0-1 priority score indicating how important this file is for the task.

    Returns a float where:
        1.0 = file is critical for the task
        0.5 = file is somewhat relevant
        0.0 = file is not needed for the task
    """
    if not task_given.strip():
        return 0.0

    try:
        response = ollama_chat_with_status(
            "Scoring files",
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a file priority scorer. "
                        "Return a single float between 0.0 and 1.0 indicating how important "
                        "this file is for implementing the given task. "
                        "1.0 = critical/essential for the task, "
                        "0.5 = moderately relevant/supporting, "
                        "0.0 = completely irrelevant. "
                        "Return ONLY the number, no explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Task to implement: {task_given}\n\n"
                        f"File name: {filename}\n"
                        f"File summary: {notes}\n\n"
                        f"File content:\n{content[:6000]}\n\n"
                        "Rate this file's importance (0.0 to 1.0). "
                        "Consider: Does this file contain the core logic that needs changing? "
                        "Is it directly involved in the task? Return only a float."
                    ),
                },
            ],
        )
        return normalize_flag(response["message"]["content"])
    except Exception as error:
        print(f"Flag generation failed for {filename}: {error}")
        return 0.0


def save_files_to_json(folder_path, output_filename="fileContent.json", task_given=""):
    """Read files from a folder and save them to a JSON file."""
    data = read_all_files_in_folder(folder_path, task_given=task_given)

    with open(output_filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    print(f"Successfully saved {len(data)} files to {output_filename}")
    return data


def print_flagged_files(data, threshold=0.5):
    """Print files whose flag score >= threshold in a clean, separated format.

    Args:
        data: List of file entries with flag scores (0.0 to 1.0)
        threshold: Minimum score to be considered flagged (default 0.5)
    """
    flagged_files = [
        item for item in data
        if float(item.get("flag", 0.0)) >= threshold
    ]
    # Sort by priority score descending
    flagged_files.sort(key=lambda x: float(x.get("flag", 0.0)), reverse=True)

    print("\n" + "=" * 80)
    print("FLAGGED FILES (Priority Ordered)")
    print("=" * 80)

    if not flagged_files:
        print(f"No files scored >= {threshold} for the current task.")
        print("=" * 80)
        return

    for index, item in enumerate(flagged_files, start=1):
        score = float(item.get("flag", 0.0))
        print(f"\n[{index}] File Name : {item['name']} (Priority: {score:.2f})")
        print("-" * 80)
        print("Notes:")
        print(item.get("notes", "").strip() or "No notes available.")
        print("-" * 80)

    print(f"Total flagged files: {len(flagged_files)}")
    print("=" * 80)
    return flagged_files


def print_refined_task(files_plan):
    """Print the per-file refined tasks in a clean terminal section."""
    print("\n" + "=" * 80)
    print("REFINED TASKS (PER FILE)")
    print("=" * 80)

    if not files_plan:
        print("No refined tasks available.")
        print("=" * 80)
        return

    for item in files_plan:
        file_name = item.get("file_name", "unknown")
        refined_task = item.get("refined_task", "")
        print(f"\nFile: {file_name}")
        print("-" * 80)
        print(refined_task.strip() or "No refined task available.")
        print("-" * 80)

    print("=" * 80)


def generate_and_save_plan(task, data, threshold=0.5):
    """Generate per-file plan JSON and save it to plan.json.

    Each file gets its own refined_task and plan specific to that file.
    Only files with flag score >= threshold are processed.

    Args:
        task: The task description
        data: List of file entries with flag scores (0.0 to 1.0)
        threshold: Minimum score to process (default 0.5)
    """
    flagged_files = [
        item for item in data
        if float(item.get("flag", 0.0)) >= threshold
    ]
    # Sort by priority descending so most important files are planned first
    flagged_files.sort(key=lambda x: float(x.get("flag", 0.0)), reverse=True)

    files_to_process = flagged_files if flagged_files else []

    if not files_to_process:
        print("No files to process.")
        save_plan([])
        return [], []

    files_plan = []
    for file_entry in files_to_process:
        file_name = file_entry.get("name", "unknown")
        priority = float(file_entry.get("flag", 0.0))
        print(f"Generating plan for: {file_name} (Priority: {priority:.2f})")

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
            "priority": priority,
        })

    save_plan(files_plan)
    return files_plan, [f["file_name"] for f in files_plan]


def build_document_id(file_entry):
    """Create a stable ID so the same file updates the same vector row."""
    digest = hashlib.md5(file_entry["name"].encode("utf-8")).hexdigest()
    return f'{file_entry["name"]}-{digest}'


def store_json_data_in_chromadb(
    data,
    db_path=CHROMA_DB_PATH,
    collection_name=None,
):
    """Store each JSON object as a separate document in ChromaDB.

    ChromaDB generates embeddings internally using its default embedding
    function, so no provider-specific embedding model is needed here.
    """
    if not data:
        print("No data found to store in ChromaDB.")
        return

    os.makedirs(db_path, exist_ok=True)
    resolved_collection_name = resolve_chroma_collection_name(
        collection_name=collection_name
    )

    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name=resolved_collection_name,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
    )

    documents = [item["content"] for item in data]
    metadatas = [
        {
            "name": item["name"],
            "source": item["name"],
            "content_length": len(item["content"]),
            "priority": float(item.get("flag", 0.0)),
            "embedding_provider": "chroma",
            "embedding_model": "default",
        }
        for item in data
    ]
    ids = [build_document_id(item) for item in data]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    print(
        f"Stored {len(data)} JSON entries in ChromaDB collection "
        f"'{resolved_collection_name}' at '{db_path}'."
    )


def Identifier_pipeline(target_folder=None, task_given=None):
    """Entry point that routes #, !, and plain chat requests."""
    target_folder = resolve_target_folder(target_folder)
    provider = choose_llm_provider()
    print(f"LLM backend: {provider}")
    print(f"Target folder: {target_folder}")
    interactive_router_loop(target_folder, initial_task=task_given)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run KittyClaw's routed terminal, coding, and chat pipelines."
    )
    parser.add_argument(
        "--target-folder",
        default=None,
        help="Folder to analyze. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Single input to route once. If omitted, KittyClaw starts an interactive session.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="LLM backend to use: openrouter or ollama. If omitted, KittyClaw will ask at startup.",
    )
    return parser.parse_args()
    

if __name__ == "__main__":
    args = parse_args()
    choose_llm_provider(preferred=args.provider)
    Identifier_pipeline(target_folder=args.target_folder, task_given=args.task)
