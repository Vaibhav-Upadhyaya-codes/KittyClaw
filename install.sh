#!/bin/bash
# KittyClaw Installer for Linux/Mac
# Install with: curl -fsSL https://raw.githubusercontent.com/your-repo/kittyclaw/main/install.sh | bash
# Or: wget -qO- https://raw.githubusercontent.com/your-repo/kittyclaw/main/install.sh | bash

set -e

KITTY_DIR="$HOME/.kittyclaw"
ENV_FILE="$KITTY_DIR/.env"

echo ""
echo "=== Kitty Claw Installer ==="
echo "Installing Kitty Claw AI Code Assistant..."
echo ""

# Create config directory
mkdir -p "$KITTY_DIR"

# Check for existing installation
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  Existing Kitty Claw configuration found: $ENV_FILE"
    read -p "Do you want to reconfigure? (y/N):" response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -f "$ENV_FILE"
    else
        echo "✅ Installation complete! Run 'kittyclaw' to start."
        exit 0
    fi
fi

# Check for Python
echo "[1/4] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ ERROR: Python 3.8+ is required but not found!"
    echo "   Please install Python from: https://python.org/downloads/"
    exit 1
fi
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo "  ✅ $PYTHON_VERSION"

# Check for pip
echo "[2/4] Checking pip..."
if $PYTHON_CMD -m pip --version &> /dev/null; then
    echo "  ✅ pip is available"
else
    echo "❌ ERROR: pip is not available"
    exit 1
fi

# Install the package
echo "[3/4] Installing kittyclaw package..."
$PYTHON_CMD -m pip install -e . --quiet 2>/dev/null || $PYTHON_CMD -m pip install -e .
echo "  ✅ Package installed successfully"

# Check for Ollama
echo "[4/4] Configuring Kitty Claw..."
if command -v ollama &> /dev/null; then
    echo "  ✅ Ollama found: available"
else
    echo "  ⚠️  Ollama not found"
    echo "   Ollama is recommended for local AI models."
    echo "   Download from: https://ollama.ai"
    echo "   After installation, run: ollama pull llama3"
fi

# Get OpenRouter API key
echo ""
echo "=== Configuration ==="
if [ -n "$OPENROUTER_API_KEY" ]; then
    API_KEY="$OPENROUTER_API_KEY"
    echo "  🔑 OpenRouter API key found in environment variable"
else
    echo "  🔑 OpenRouter API key not found in environment."
    echo "   Get one at: https://openrouter.ai/keys"
    read -p "   Enter your OpenRouter API key (or press Enter to skip): " API_KEY
fi

if [ -n "$API_KEY" ]; then
    API_KEY=$(echo "$API_KEY" | tr -d '[:space:]')
    if [[ "$API_KEY" =~ ^sk-[a-zA-Z0-9]+$ ]]; then
        cat > "$ENV_FILE" << EOF
# Kitty Claw Configuration
OPENROUTER_API_KEY=$API_KEY
OLLAMA_HOST=http://localhost:11434
EOF
        echo "  ✅ Configuration saved to: $ENV_FILE"
    else
        echo "  ⚠️  WARNING: API key format looks invalid (should start with 'sk-')"
        echo "   You can set it later by running: export OPENROUTER_API_KEY='your-key'"
    fi
else
    echo "  ⚠️  No API key configured."
    echo "   Set it with: export OPENROUTER_API_KEY='your-key'"
    echo "   Or edit: $ENV_FILE"
fi

echo ""
echo "=== Installation Complete ==="
echo "✅ Run 'kittyclaw' to launch Kitty Claw!"
echo "   Configuration directory: $KITTY_DIR"
echo ""
