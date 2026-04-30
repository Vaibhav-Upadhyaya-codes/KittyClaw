import os
import shutil
import subprocess
import sys
import time

ACCENT = "\033[38;2;50;205;194m"
BG = "\033[48;2;11;16;32m"
RESET = "\033[0m"

KITTY_OPEN_LINES = [
    "  ▄█    █▄",
    "████████████        ",
    "███▄████▄███        ",
    "████████████ ███    ",
    "████████████        ",
    "  █      █          ",
    "  █      █          ",
]

KITTY_BLINK_LINES = [
    "  ▄█    █▄",
    "████████████        ",
    "███▄████████        ",
    "████████████ ███    ",
    "████████████        ",
    "  █      █          ",
    "  █      █          ",
]


def enable_ansi():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _colorize(lines):
    width = max(len(line) for line in lines)
    return "\n".join(f"{BG}{ACCENT}{line.ljust(width)}{RESET}" for line in lines)


KITTY_STATIC = _colorize(KITTY_OPEN_LINES)
KITTY_FRAME_1 = _colorize(KITTY_OPEN_LINES)
KITTY_FRAME_2 = _colorize(KITTY_BLINK_LINES)


def render_kitty():
    enable_ansi()
    print(KITTY_STATIC)


def render_kitty_blink(cycles=4, open_delay=0.65, blink_delay=0.12):
    enable_ansi()
    frames = (
        (KITTY_FRAME_1, open_delay),
        (KITTY_FRAME_2, blink_delay),
        (KITTY_FRAME_1, blink_delay),
    )
    sys.stdout.write("\033[?25l")
    try:
        for _ in range(max(1, cycles)):
            for frame, delay in frames:
                sys.stdout.write("\033[H\033[J")
                print(frame)
                sys.stdout.flush()
                time.sleep(delay)
    finally:
        sys.stdout.write(RESET + "\033[?25h")
        sys.stdout.flush()


def _term_width():
    return shutil.get_terminal_size((80, 24)).columns


def _center(text):
    width = _term_width()
    return "\n".join(line.center(width) for line in text.splitlines())


def _panel_line(text=""):
    inner = 54
    clipped = text[:inner]
    return f"{BG}{ACCENT}[ {clipped.ljust(inner)} ]{RESET}"


def _header():
    title = f"{BG}{ACCENT} KITTY CLAW // TERMINAL AI {RESET}"
    subtitle = f"{BG}{ACCENT} cute shell, same brain, smoother flow {RESET}"
    return "\n".join((_center(title), _center(subtitle)))


def _menu():
    items = [
        "1. Run full pipeline (identify + rectify)",
        "2. Run rectification only",
        "3. Blink mascot",
        "4. Show mascot",
        "5. Exit",
    ]
    return "\n".join(_center(_panel_line(item)) for item in items)


def _banner():
    flow_note = _center(_panel_line("main.py now continues into rectification automatically"))
    return "\n".join((_header(), "", _center(KITTY_STATIC), "", flow_note, "", _menu()))


def clear_screen():
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def _run_script(args):
    subprocess.run([sys.executable] + args, check=False)


def launch_tui():
    enable_ansi()
    while True:
        clear_screen()
        print(_banner())
        print()
        choice = input(f"{ACCENT}Select an option > {RESET}").strip()

        if choice == "1":
            clear_screen()
            _run_script(["main.py"])
            input(f"\n{ACCENT}Press Enter to return to Kitty Claw...{RESET}")
        elif choice == "2":
            task = input(f"{ACCENT}Enter rectification task > {RESET}").strip()
            if task:
                clear_screen()
                _run_script(["rectification.py", task])
            input(f"\n{ACCENT}Press Enter to return to Kitty Claw...{RESET}")
        elif choice == "3":
            render_kitty_blink()
            input(f"\n{ACCENT}Press Enter to return to Kitty Claw...{RESET}")
        elif choice == "4":
            clear_screen()
            print(_center(KITTY_STATIC))
            input(f"\n{ACCENT}Press Enter to return to Kitty Claw...{RESET}")
        elif choice == "5":
            clear_screen()
            print(_center(KITTY_FRAME_2))
            break
        else:
            input(f"{ACCENT}Unknown option. Press Enter and try again...{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--blink":
        render_kitty_blink()
    elif len(sys.argv) > 1 and sys.argv[1] == "--static":
        render_kitty()
    else:
        launch_tui()
