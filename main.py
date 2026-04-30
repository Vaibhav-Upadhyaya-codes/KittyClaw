import hashlib
import json
import os
import chromadb
import ollama
from chatbot import *
from rectification import rectification

path_of_target_folder = r"C:\Users\Vaibhav Upadhyaya\OneDrive\Documents\MASTER\terminalAi"

DEFAULT_DB_ROOT = os.environ.get("LOCALAPPDATA", os.getcwd())
CHROMA_DB_PATH = os.path.join(DEFAULT_DB_ROOT, "SoftMother", "chroma_db")
COLLECTION_NAME = "file_contents"
# This is already available locally and works with `ollama.embed` in this setup.
EMBED_MODEL = "llama3:8b"

MODEL = "qwen3.5:397b-cloud"
SUMMARY_MODEL = "qwen3.5:397b-cloud"
FLAG_MODEL = "qwen3.5:397b-cloud"
TASK_GIVEN = input("How can i help : ")


def read_all_files_in_folder(folder_path, task_given=TASK_GIVEN):
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
        response = ollama.chat(
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
        response = ollama.chat(
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


def save_files_to_json(folder_path, output_filename="fileContent.json", task_given=TASK_GIVEN):
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


def generate_embeddings(documents, model_name=EMBED_MODEL):
    """Generate embeddings for a list of documents using Ollama."""
    try:
        response = ollama.embed(model=model_name, input=documents)
    except Exception as error:
        raise RuntimeError(
            f"Could not generate embeddings with Ollama model '{model_name}'. "
            "Make sure Ollama is running and the embedding model is available. "
            f"For example: `ollama pull {model_name}`. Original error: {error}"
        ) from error

    return response["embeddings"]


def store_json_data_in_chromadb(
    data,
    db_path=CHROMA_DB_PATH,
    collection_name=COLLECTION_NAME,
    embed_model=EMBED_MODEL,
):
    """Store each JSON object as a separate document in ChromaDB."""
    if not data:
        print("No data found to store in ChromaDB.")
        return

    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(name=collection_name)

    documents = [item["content"] for item in data]
    metadatas = [
        {
            "name": item["name"],
            "source": item["name"],
            "content_length": len(item["content"]),
            "priority": float(item.get("flag", 0.0)),
        }
        for item in data
    ]
    ids = [build_document_id(item) for item in data]
    embeddings = generate_embeddings(documents, model_name=embed_model)

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    print(
        f"Stored {len(data)} JSON entries in ChromaDB collection "
        f"'{collection_name}' at '{db_path}'."
    )


def Identifier_pipeline():
    data = save_files_to_json(path_of_target_folder, task_given=TASK_GIVEN)
    print_flagged_files(data)
    store_json_data_in_chromadb(data)
    files_plan, file_names = generate_and_save_plan(TASK_GIVEN, data)
    print_refined_task(files_plan)
    print(f"Saved {len(files_plan)} file plans to plan.json")
    

if __name__ == "__main__":
    Identifier_pipeline()