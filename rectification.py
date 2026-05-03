import argparse
import json
import os
from chatbot import implementing_changes, get_file_content_from_chromadb, validate_plan_against_task

# Minimum relevance score for a step to be executed (0.0 to 1.0)
# Steps below this threshold are skipped as they don't directly implement the task
STEP_RELEVANCE_THRESHOLD = 0.7


def resolve_target_folder(target_folder_path=None):
    """Return the folder whose files should be modified."""
    return os.path.abspath(target_folder_path or os.getcwd())


def rectification(target_folder_path, task_given):
    """Execute the rectification pipeline strictly based on the user's original task.

    Only files and steps that directly contribute to the task are processed.
    Steps are validated against the task before execution.

    Args:
        target_folder_path: Path to the target folder containing files to modify
        task_given: The original user task that drives what changes should be made
    """
    target_folder_path = resolve_target_folder(target_folder_path)

    with open("plan.json", "r") as f:
        data = json.load(f)

    # Validate that the plan actually addresses the user's task
    print("=" * 80)
    print("USER TASK:", task_given)
    print("TARGET FOLDER:", target_folder_path)
    print("=" * 80)
    print(f"Step relevance threshold: {STEP_RELEVANCE_THRESHOLD} (steps below this will be skipped)")
    print("=" * 80)

    # Sort files by priority (highest first) if priority field exists
    files_sorted = sorted(
        data.get("files", []),
        key=lambda x: float(x.get("priority", 0.0)),
        reverse=True
    )

    for file in files_sorted:
        file_priority = float(file.get("priority", 0.0))
        print(f"\nFILE: {file['file_name']} (Priority: {file_priority:.2f})")
        print("-" * 80)

        # Retrieve file content from ChromaDB
        file_data = get_file_content_from_chromadb(file["file_name"])

        if not file_data:
            print(f"WARNING: Could not retrieve '{file['file_name']}' from ChromaDB - skipping")
            continue

        # Validate and execute each step against the user's task
        valid_count = 0
        skipped_count = 0

        for step in file.get("plan", []):
            step_desc = step.get("step", "")

            # Validate this step contributes to the user's task
            step_relevance = validate_plan_against_task(
                task_given,
                file.get("refined_task", ""),
                step_desc
            )

            if step_relevance >= STEP_RELEVANCE_THRESHOLD:
                # Print and execute immediately
                print(f"\n  STEP: {step_desc}")
                print(f"  TOOLS: {step.get('tools', [])}")
                print(f"  RELEVANCE: {step_relevance:.2f} - EXECUTING...")

                path = os.path.join(target_folder_path, file["file_name"])
                # Read fresh content from disk for each step (since file changes after each edit)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        current_content = f.read()
                except Exception as e:
                    print(f"  STATUS: ERROR reading file - {e}")
                    continue

                try:
                    implementing_changes(current_content, step["step"], path)
                    print(f"  STATUS: Completed")
                    valid_count += 1
                except Exception as e:
                    print(f"  STATUS: ERROR - {e}")
            else:
                print(f"\n  STEP: {step_desc}")
                print(f"  RELEVANCE: {step_relevance:.2f} - SKIPPED (below threshold)")
                skipped_count += 1

        # Summary for this file
        if valid_count > 0:
            print(f"\n  Executed {valid_count} step(s) for {file['file_name']}")
        else:
            print(f"\n  No steps executed for {file['file_name']}")

        if skipped_count > 0:
            print(f"  Skipped {skipped_count} step(s) not directly related to task")

        print("=" * 80)

    print("\nRectification complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run KittyClaw rectification for the selected folder."
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task description. If omitted, KittyClaw will prompt for it.",
    )
    parser.add_argument(
        "--target-folder",
        default=None,
        help="Folder containing files to modify. Defaults to the current working directory.",
    )
    args = parser.parse_args()

    task = args.task or input("Enter task: ").strip()
    rectification(args.target_folder, task)
