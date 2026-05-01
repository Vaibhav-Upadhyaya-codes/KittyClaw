import argparse
import atexit
import json
import os
import subprocess

from chatbot import extract_json_text, normalize_plan, ollama_chat_with_status

MODEL = "qwen3.5:397b-cloud"
JSON_FILE = "instance.json"
TERMINAL_PLAN_FILE = "terminal_plan.json"
DEFAULT_MAX_ITERATIONS = 20

_ps_process = None


def _escape_powershell_single_quotes(value):
    """Escape single quotes for PowerShell single-quoted strings."""
    return str(value).replace("'", "''")


def close_persistent_powershell():
    """Close the persistent PowerShell process if it exists."""
    global _ps_process

    if _ps_process is None:
        return

    try:
        if _ps_process.stdin:
            _ps_process.stdin.write("exit\n")
            _ps_process.stdin.flush()
        _ps_process.wait(timeout=5)
    except Exception:
        try:
            _ps_process.kill()
        except Exception:
            pass
    finally:
        _ps_process = None


atexit.register(close_persistent_powershell)


def get_persistent_powershell(working_directory=None):
    """Get or create a persistent PowerShell process."""
    global _ps_process

    if _ps_process is None:
        _ps_process = subprocess.Popen(
            ["powershell", "-NoLogo", "-NoExit", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=working_directory or os.getcwd(),
        )

    return _ps_process


def load_json_data():
    """Load existing command history from JSON file."""
    if os.path.exists(JSON_FILE) and os.path.getsize(JSON_FILE) > 0:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []


def reset_json_data():
    """Start a fresh command history for a new terminal task."""
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump([], file, indent=2)


def save_to_json(command, result):
    """Save command execution details to JSON file."""
    data = load_json_data()
    data.append(
        {
            "command": command,
            "result": result,
        }
    )
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def save_terminal_plan(task, plan, output_path=TERMINAL_PLAN_FILE):
    """Persist the generated terminal plan."""
    payload = {
        "task": task,
        "plan": plan,
    }
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def print_terminal_plan(task, plan):
    """Print the terminal execution plan in a readable format."""
    print("\n" + "=" * 80)
    print("TERMINAL EXECUTION PLAN")
    print("=" * 80)
    print(f"Task: {task}")

    if not plan:
        print("No plan steps were generated.")
        print("=" * 80)
        return

    for index, item in enumerate(plan, start=1):
        tools = ", ".join(item.get("tools", [])) or "PowerShell"
        print(f"\n[{index}] {item.get('step', '').strip()}")
        print(f"Tools: {tools}")

    print("=" * 80)


def clean_command(command):
    """Clean and normalize a model-generated PowerShell command."""
    cleaned = str(command or "").strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    if (
        cleaned.startswith('"') and cleaned.endswith('"')
    ) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()

    lowered = cleaned.lower()
    if lowered.startswith("powershell"):
        cleaned = cleaned[len("powershell"):].strip()
        lowered = cleaned.lower()

    if lowered.startswith("-command"):
        cleaned = cleaned[len("-command"):].strip()

    return cleaned.strip()


def is_valid_command(command):
    """Basic validation for generated commands."""
    if not command or len(command) < 2:
        return False

    if command == "TASK COMPLETE":
        return True

    single_quotes = command.count("'") - command.count("\\'")
    double_quotes = command.count('"') - command.count('\\"')

    return single_quotes % 2 == 0 and double_quotes % 2 == 0


def execute_powershell_command(command, working_directory=None):
    """Execute a PowerShell command in the persistent session and return output."""
    try:
        ps = get_persistent_powershell(working_directory=working_directory)
        marker = "<<<END_OF_COMMAND_OUTPUT>>>"
        if working_directory:
            escaped_path = _escape_powershell_single_quotes(
                os.path.abspath(working_directory)
            )
            full_command = (
                f"Set-Location -LiteralPath '{escaped_path}'; "
                f"{command}; "
                f"Write-Host '{marker}'\n"
            )
        else:
            full_command = f"{command}; Write-Host '{marker}'\n"

        ps.stdin.write(full_command)
        ps.stdin.flush()

        output = ""
        while True:
            char = ps.stdout.read(1)
            if not char:
                break
            output += char
            if marker in output:
                output = output.split(marker)[0]
                break

        return output.strip()
    except Exception as error:
        return f"Error executing command: {error}"


def generate_terminal_plan(task):
    """Generate a step-by-step plan for a terminal automation task."""
    response = ollama_chat_with_status(
        "Planning terminal task",
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a planner for a terminal automation agent. "
                    "Return only valid JSON. "
                    "The JSON must be an array. "
                    "Each array item must have exactly these keys: "
                    '"step" and "tools". '
                    '"step" must be a concise, concrete action. '
                    '"tools" must be an array of strings. '
                    "Keep the plan strict to the user's request. "
                    "Do not include markdown fences or any explanation outside JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Create a terminal-first execution plan for the following task.\n\n"
                    f"Task: {task}\n\n"
                    "The plan should help an automated PowerShell agent complete the task safely, "
                    "one command at a time."
                ),
            },
        ],
    )

    raw_text = response["message"]["content"]
    json_text = extract_json_text(raw_text)

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return []

    return normalize_plan(parsed)


def generate_command(task, plan, working_directory):
    """Generate a single next PowerShell command for the task."""
    history = load_json_data()
    plan_text = json.dumps(plan, indent=2, ensure_ascii=False)
    history_text = json.dumps(history, indent=2, ensure_ascii=False)

    response = ollama_chat_with_status(
        "Choosing terminal command",
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a PowerShell command writer. "
                    "Return exactly one PowerShell command, or return TASK COMPLETE if the task is finished. "
                    "Do not include markdown, code fences, labels, or explanations. "
                    "Use the existing command history to avoid repeating failed work. "
                    "Prefer inspecting files before changing them when needed."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: {task}\n\n"
                    f"Working directory: {working_directory}\n\n"
                    f"Plan:\n{plan_text}\n\n"
                    f"Command history with results:\n{history_text}\n\n"
                    "Return only the single best next PowerShell command. "
                    "If the task is fully completed, return TASK COMPLETE."
                ),
            },
        ],
    )

    return clean_command(response["message"]["content"])


def normalize_terminal_task(task):
    """Remove the routing prefix if the task starts with #."""
    normalized = (task or "").strip()
    if normalized.startswith("#"):
        normalized = normalized[1:].strip()
    return normalized


def run_terminal_task(task, target_folder=None, max_iterations=DEFAULT_MAX_ITERATIONS):
    """Run a terminal-only task by first planning it, then executing commands."""
    working_directory = os.path.abspath(target_folder or os.getcwd())
    normalized_task = normalize_terminal_task(task)

    if not normalized_task:
        print("Terminal task cannot be empty.")
        return []

    reset_json_data()
    close_persistent_powershell()

    plan = generate_terminal_plan(normalized_task)
    save_terminal_plan(normalized_task, plan)
    print_terminal_plan(normalized_task, plan)

    print("\n" + "=" * 80)
    print("STARTING TERMINAL AUTOMATION")
    print("=" * 80)
    print(f"Working directory: {working_directory}")

    completed = False

    try:
        for iteration in range(1, max_iterations + 1):
            print(f"\nIteration {iteration}/{max_iterations}")
            command = generate_command(normalized_task, plan, working_directory)

            if command == "TASK COMPLETE":
                print("Task completed by terminal agent.")
                completed = True
                break

            if not is_valid_command(command):
                print(f"Invalid command generated: {command}")
                save_to_json(command, "Skipped because the command was invalid.")
                continue

            print(f"[Executing] {command}")
            result = execute_powershell_command(command, working_directory=working_directory)
            print(result or "(no output)")
            save_to_json(command, result)
    finally:
        close_persistent_powershell()

    if not completed:
        print(
            f"Stopped after {max_iterations} iterations. "
            "Review instance.json and terminal_plan.json for the last state."
        )

    return plan


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a terminal-only task with planning and command execution."
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task description. Prefixing with # is optional when calling terminalAccess directly.",
    )
    parser.add_argument(
        "--target-folder",
        default=None,
        help="Working directory for the terminal agent. Defaults to the current directory.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help="Maximum number of commands the terminal agent may execute.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    task = args.task or input("Enter terminal task: ").strip()
    run_terminal_task(
        task=task,
        target_folder=args.target_folder,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()
