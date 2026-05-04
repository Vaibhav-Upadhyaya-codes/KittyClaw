#!/usr/bin/env python3
from setuptools import setup

PY_MODULES = [
    "chatbot",
    "kitty_mascot",
    "main",
    "rectification",
    "terminalAccess",
]

setup(
    name="kittyclaw",
    version="0.2.2",
    description="Kitty Claw - AI-powered code rectification agent with a cute terminal mascot",
    author="Vaibhav Upadhyaya",
    python_requires=">=3.8",
    py_modules=PY_MODULES,
    install_requires=[
        "ollama>=0.1.0",
        "chromadb>=0.4.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "kittyclaw=kitty_mascot:launch_tui",
        ],
    },
)
