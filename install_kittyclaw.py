#!/usr/bin/env python3
"""
KittyClaw Installer
Installs the kittyclaw command to your system.
"""

import os
import subprocess
import sys
import winreg

def get_scripts_dir():
    """Get the directory where pip installs scripts."""
    return os.path.dirname(sys.executable)

def add_to_path_windows(path_to_add):
    """Add directory to Windows user PATH."""
    try:
        # Get current PATH
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_ALL_ACCESS
        )
        current_path, _ = winreg.QueryValueEx(key, "Path")

        if path_to_add not in current_path:
            new_path = current_path + ";" + path_to_add
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print(f"  Added to PATH: {path_to_add}")
            print("  NOTE: Restart your terminal for PATH changes to take effect.")
        else:
            print("  PATH already contains scripts directory.")

        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        # Environment key doesn't exist, create it
        try:
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                "Environment",
                0,
                winreg.KEY_ALL_ACCESS
            )
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, path_to_add)
            winreg.CloseKey(key)
            print(f"  Created PATH with: {path_to_add}")
            return True
        except Exception as e:
            print(f"  Error creating PATH: {e}")
            return False
    except Exception as e:
        print(f"  Error updating PATH: {e}")
        return False

def install():
    """Install kittyclaw package."""
    print("\n" + "=" * 60)
    print("  KITTY CLAW INSTALLER")
    print("=" * 60)

    # Check if we're in the right directory
    if not os.path.exists("pyproject.toml") and not os.path.exists("setup.py"):
        print("\nError: pyproject.toml or setup.py not found!")
        print("Please run this script from the KittyClaw directory.")
        sys.exit(1)

    # Install using pip
    print("\nInstalling kittyclaw package...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"\nInstallation failed!")
        print(result.stderr)
        sys.exit(1)

    print("\nInstallation successful!")

    # Show the scripts directory
    scripts_dir = get_scripts_dir()
    exe_path = os.path.join(scripts_dir, "kittyclaw.exe")

    print(f"\n  kittyclaw command installed to: {scripts_dir}")

    # Check if scripts dir is in PATH
    path_env = os.environ.get("PATH", "")
    if scripts_dir not in path_env:
        print("\n  WARNING: Scripts directory not in PATH!")
        print("\n  Would you like to add it automatically? (y/n): ", end="")
        try:
            choice = input().strip().lower()
            if choice == 'y':
                if add_to_path_windows(scripts_dir):
                    print("\n  PATH updated! Please restart your terminal.")
            else:
                print(f"\n  To use 'kittyclaw' from anywhere, add to PATH:")
                print(f"    {scripts_dir}")
        except EOFError:
            pass
    else:
        print("\n  Scripts directory is already in PATH!")

    print("\n" + "=" * 60)
    print("  You can now run 'kittyclaw' from any terminal!")
    print("  Or use: python kitty_mascot.py")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    install()
