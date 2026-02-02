# Geofeed Tuner – AI Skills for Better IP Geolocation Feeds

[![Download ZIP](https://img.shields.io/badge/Download%20ZIP-8A2BE2)](https://github.com/fastah/ip-geofeed-skills/archive/refs/heads/main.zip)

This package has self-help resources from Siddharth "Sid" Mathur's talk at [NANOG 96](https://nanog.org/events/nanog-96/) San Francisco - [High-quality IP Geofeeds using AI Coding Assistants and MCP](https://nanog.org/events/nanog-96/content/5683/).

**Geofeed Tuner** helps you create, refine, and improve IP geolocation feeds. It goes beyond simple RFC 8805 compliance checking to offer opinionated recommendations based on real-world deployment experience.

AI coding agents should be asked to read the tuning guidance in [SKILL.md](skills/geofeed-tuner/SKILL.md).

## Pre-requisites

- IDE - [Visual Studio Code](https://code.visualstudio.com).
- For [GitHub Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat), enable the experimental [`chat.useAgentSkills`](vscode://settings/chat.useAgentSkills) feature, see [Agent Skills help](https://code.visualstudio.com/docs/copilot/customization/agent-skills). Related [VS Code config file](.vscode/settings.json).

- For [Claude Code](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code) - enable [Skills in Settings -> Capabilities](https://support.claude.com/en/articles/12512180-using-skills-in-claude). Then make a `geofeed-tuner.zip` ZIP file from the [`skills/geofeed-tuner`](skills/geofeed-tuner) folder, and upload it as an Agent Skill. Enterprise users must also enable `Code execution and file creation`.

- For [ChatGPT Codex](https://marketplace.visualstudio.com/items?itemName=openai.chatgpt), enable [Skills](https://developers.openai.com/codex/skills/) with the `[[skills.config]]` flag.

- *Windows only*: Use the Microsoft Store for self-updating [VS Code](https://apps.microsoft.com/detail/xp9khm4bk9fz7q?hl=en-US&gl=US), [Python](https://apps.microsoft.com/detail/9pnrbtzxmb4z?hl=en-US&gl=US), and [PowerShell](https://apps.microsoft.com/detail/9mz1snwt0n5d?hl=en-US&gl=US).

## Quick guide

[![Download ZIP](https://img.shields.io/badge/Download%20ZIP-8A2BE2)](https://github.com/fastah/ip-geofeed-skills/archive/refs/heads/main.zip)

- Download and unzip this repository.
- Launch [Visual Studio Code](https://code.visualstudio.com)
- Within VS Code, open the folder via File menu (top left) -> Open Folder.
- Install the VS Code extension for your favourite AI coding agent from the Pre-requisites section (above).
- Click the "Chat" icon on the left navigation bar for GitHub CoPilot (or the alternative agent's chat icon)
- Type the following prompt to get started

```
Hey chat, help me get started with the "Geofeed Tuner" agent skill from the SKILL.md file! :)
```

## What are (AI) Agent Skills

AI [Agent Skills](https://agentskills.io/home) is an open standard that works across multiple AI tools to make domain-specific knowledge easier to share - which in this repository's case is IP Geolocation feed tuning and improvement. 

Partial list of AI tools that support Agent Skills:

- [GitHub Copilot](https://code.visualstudio.com/docs/copilot/customization/agent-skills) - VS Code, Copilot CLI, coding agent
- [Cursor](https://cursor.com/docs/context/skills)
- [Claude Code](https://code.claude.com/docs/en/skills)
- [Amp Code](https://ampcode.com/news/agent-skills) - VS Code and Amp CLI

## Troubleshooting

1. VS Code - turn ON the experimental Agent Skills flag ([config](.vscode/settings.json)).

## Recommended Extensions

### VS Code

These are automatically suggested via the included [extensions hint](.vscode/extensions.json).

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python) | Microsoft | Python configuration + syntax highlighting |
| [Go](https://marketplace.visualstudio.com/items?itemName=golang.go) | Go Team at Google | Go (Golang.org) configuration + syntax highlighting |
| [Rainbow CSV](https://marketplace.visualstudio.com/items?itemName=mechatroner.rainbow-csv) | mechatroner | CSV syntax highlighting |
| [PowerShell](https://marketplace.visualstudio.com/items?itemName=ms-vscode.PowerShell) | Microsoft | [Windows only] Modern scripting system |

## Advanced usage

### Amp

Install the skill directly from GitHub:
```shell
amp install github.com/fastah/ip-geofeed-skills/geofeed-tuner
```
Then invoke it with:
```
/skill geofeed-tuner
```

Or simply ask Amp to tune a geofeed and it will auto-select the skill.

### GitHub CoPilot CLI

You can use [CoPilot's CLI mode](https://github.com/features/copilot/cli) to work with [Agent Skills](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli#customizing-github-copilot-cli). 
