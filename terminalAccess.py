from time import sleep, time

import ollama
import json
import subprocess
import os

JSON_FILE = 'instance.json'

# Global persistent PowerShell session
_ps_process = None

def get_persistent_powershell():
    """Get or create a persistent PowerShell process"""
    global _ps_process
    if _ps_process is None:
        _ps_process = subprocess.Popen(
            ['powershell', '-NoExit', '-Command', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    return _ps_process

def tyyping_effect(text):
    """Simulate typing effect in terminal"""
    for char in text:
        print(char, end='', flush=True)
        sleep(0.02)  # Adjust typing speed here
    print()  # New line after finishing

def load_json_data():
    """Load existing data from JSON file or create empty list"""
    if os.path.exists(JSON_FILE) and os.path.getsize(JSON_FILE) > 0:
        with open(JSON_FILE, 'r') as f:
            return json.load(f)
    return []

def save_to_json(command, result):
    """Save command and result to JSON file"""
    data = load_json_data()
    data.append({
        'command': command,
        'result': result
    })
    with open(JSON_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def generate_command(task):
    stream = ollama.chat(
        model='qwen3.5:397b-cloud',
        messages=[{'role':'user','content':f'''you are a powershell command writer
                   -write powershell command as per the task given
                   -you will be given context history of the commands that have been executed and there output
                   -only return one command at a time 
                   -if the task is complete return TASK COMPLETE
                   
                   task: {task}
                   context history: {json.dumps(load_json_data())}
                   '''
                   }],
        stream=True
    )
    return stream

def extract_command(command):
    stream = ollama.chat(
        model='qwen3.5:397b-cloud',
        messages=[{'role':'user','content':f'extract powershell command from the following text: {command}, only return the command without any explanation'}],
        stream=True
    )
    return stream

def clean_command(cmd):
    """Clean and validate the command"""
    # Strip whitespace
    cmd = cmd.strip()
    
    # Remove leading/trailing quotes if present
    if (cmd.startswith('"') and cmd.endswith('"')) or (cmd.startswith("'") and cmd.endswith("'")):
        cmd = cmd[1:-1]
    
    # Remove common LLM artifacts
    if cmd.lower().startswith("powershell"):
        cmd = cmd[len("powershell"):].strip()
    if cmd.lower().startswith("-command"):
        cmd = cmd[len("-command"):].strip()
    
    return cmd.strip()

def is_valid_command(cmd):
    """Check if command looks valid (basic validation)"""
    if not cmd or len(cmd) < 2:
        return False
    
    # Check for unmatched quotes
    single_quotes = cmd.count("'") - cmd.count("\\'")
    double_quotes = cmd.count('"') - cmd.count('\\"')
    
    # Quotes should be even (matched pairs)
    if single_quotes % 2 != 0 or double_quotes % 2 != 0:
        return False
    
    return True

def execute_powershell_command(command):
    """Execute PowerShell command in persistent session and return output"""
    try:
        ps = get_persistent_powershell()
        
        # Send command and a marker to know when it's done
        marker = "<<<END_OF_COMMAND_OUTPUT>>>"
        full_command = f"{command}; Write-Host '{marker}'\n"
        
        ps.stdin.write(full_command)
        ps.stdin.flush()
        
        # Read output until we see the marker
        output = ""
        while True:
            char = ps.stdout.read(1)
            if not char:
                break
            output += char
            if marker in output:
                # Remove the marker and everything after it
                output = output.split(marker)[0]
                break
        
        return output.strip()
    except Exception as e:
        return f"Error executing command: {str(e)}"

while True:
    think = generate_command(r"C:\Users\Vaibhav Upadhyaya\OneDrive\Documents\MASTER\terminalAi\test.py  go to this file and read its content it has a error fix that error plaese ")
    
    # Extract command from think stream
    think_output = ""
    for chunk in think:
        think_output += chunk['message']['content']
    
    if "TASK COMPLETE" in think_output:
        tyyping_effect("Task completed")
        # Clean up PowerShell session
        if _ps_process:
            _ps_process.stdin.write("exit\n")
            _ps_process.stdin.flush()
            _ps_process.wait()
            _ps_process = None
        break
    
    command_stream = extract_command(think_output)

    output = ""
    for chunk in command_stream:
        output += chunk['message']['content']
        tyyping_effect(chunk['message']['content'])
    
    # Clean the command
    output = clean_command(output)
    output = output.replace('`', '').replace('powershell', '')
    
    print(f"\n[Executing command]: {output}\n")
    
    # Validate command before executing
    if not is_valid_command(output):
        tyyping_effect("[ERROR] Invalid command - skipping execution\n")
        continue
    
    # Execute the command and get result
    result = execute_powershell_command(output)
    
    tyyping_effect(f"\n--- Command Output ---\n{result}\n")
    # Save command and result to JSON file
    save_to_json(output, result)
    
    tyyping_effect(f"\n--- Command saved to JSON ---\n")

