# KittyClaw Command Installation

## Quick Start

After running the installer, you can use `kittyclaw` from any terminal:

```bash
kittyclaw
```

## Installation Methods

### Method 1: Python Package (Recommended)

Run the installer:

```bash
python install_kittyclaw.py
```

This installs `kittyclaw.exe` to your Python Scripts directory.

**If Scripts directory is not in PATH**, you have two options:

1. **Add to PATH permanently** (Windows):
   ```powershell
   # Run in PowerShell as your user (not admin)
   $env:PATH += ";C:\Users\Vaibhav Upadhyaya\AppData\Roaming\Python\Python311\Scripts"
   [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\Users\Vaibhav Upadhyaya\AppData\Roaming\Python\Python311\Scripts", "User")
   ```

2. **Copy the batch file** to an existing PATH location:
   ```bash
   # Copy kittyclaw.bat and kitty_mascot.py to a folder in PATH
   copy kittyclaw.bat C:\Windows\
   copy kitty_mascot.py C:\Windows\
   ```

### Method 2: Direct Python Execution

Always works without installation:

```bash
python kitty_mascot.py
```

## Command Line Options

```bash
# Interactive TUI menu (default)
kittyclaw

# Show static mascot
kittyclaw --static

# Show blinking animation
kittyclaw --blink
```

## TUI Features

The interactive menu provides:

1. **Run full pipeline** - Execute main.py + rectification.py
2. **Run rectification only** - Apply fixes using existing plan.json
3. **Blink mascot** - Animated mascot display
4. **Show mascot** - Static mascot display
5. **Exit** - Close with goodbye animation

## Troubleshooting

### "kittyclaw: command not found"

The Scripts directory isn't in your PATH. Find where it was installed:

```bash
python -c "import sys; print(sys.prefix + '\\Scripts')"
```

Then either:
- Add that directory to PATH
- Copy `kittyclaw.bat` to an existing PATH directory
- Use `python kitty_mascot.py` directly

### ANSI colors not showing on Windows

The mascot includes automatic ANSI enablement for Windows 10+. If colors don't show:

```powershell
# Enable VT100 processing
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f
```
