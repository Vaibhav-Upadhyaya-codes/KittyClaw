# Kitty Claw

🐱 **AI-powered code rectification agent with a cute terminal mascot**

Kitty Claw helps you identify and fix issues in your codebase. It combines AI-powered code analysis with an adorable terminal interface to make debugging more enjoyable.

## Installation

### Quick Install (Recommended)

Run one of these commands to install Kitty Claw:

**For macOS/Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/your-repo/kittyclaw/main/install.sh | bash
```

**For Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

### Manual Install

1. Clone this repository
2. Install dependencies:
```bash
pip install -e .
```

3. Configure your API key:
```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY="your-api-key-here"
```

4. Run Kitty Claw:
```bash
kittyclaw
```

## Requirements

- **Python 3.8+**
- **OpenRouter API Key** (for AI functionality)
- **Optional**: [Ollama](https://ollama.ai) for local AI models

## Getting Started

1. **Get your API key** from [OpenRouter.ai](https://openrouter.ai/keys)
2. **Run the installer** - it will prompt for your API key
3. **Launch with `kittyclaw`** - the terminal mascot will guide you

## Features

- 🐱 Cute terminal mascot with animations
- 🤖 AI-powered code analysis
- 🔄 Automatic code rectification
- 🎨 Beautiful terminal interface
- 💾 Configuration management

## Configuration

Kitty Claw will create a `.env` file in `~/.kittyclaw` with your settings:

```env
OPENROUTER_API_KEY=your-api-key-here
OLLAMA_HOST=http://localhost:11434
```

### Environment Variables

- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `OLLAMA_HOST`: Ollama server URL (default: http://localhost:11434)

## Usage

Launch Kitty Claw to see the interactive menu:

1. **Run full pipeline** - Identifies and rectifies issues
2. **Rectification only** - Fix specific issues
3. **Blink mascot** - Just for fun!
4. **Show mascot** - Display the static kitty
5. **Exit** - Close Kitty Claw

## Development

### Installing Development Dependencies

```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## Contributing

Feel free to open issues and submit pull requests!

## License

Apache-2.0

## Troubleshooting

### Installation Issues

- Ensure Python 3.8+ is installed
- Check if pip is available
- Verify your API key format (should start with `sk-`)

### Running Issues

- Make sure your OpenRouter API key is set
- If using Ollama, ensure it's running
- Check the terminal compatibility (ANSI colors required)

## Support

- Report bugs: [GitHub Issues](https://github.com/your-repo/kittyclaw/issues)
- Documentation: [Wiki](https://github.com/your-repo/kittyclaw/wiki)
- Community: [Discussions](https://github.com/your-repo/kittyclaw/discussions)