# AI skills for IP Geolocation feeds - authoring, validating, and publication

Self-help resources from Siddharth "Sid" Mathur's talk at [NANOG 96](https://nanog.org/events/nanog-96/) San Francisco - [High-quality IP Geofeeds using AI Coding Assistants and MCP](https://nanog.org/events/nanog-96/content/5683/).

## Pre-requisites

- Visual Studio Code - enable the [experimental `chat.useAgentSkills`](vscode://settings/chat.useAgentSkills) feature, see [Agent Skills help](https://code.visualstudio.com/docs/copilot/customization/agent-skills).

- Claude - [turn on Skills in Settings -> Capabilities](https://support.claude.com/en/articles/12512180-using-skills-in-claude). Enterprise users must also enable `Code execution and file creation`. Claude Code supports Skills in beta.

## Quick guide

### Amp

Install the skill directly from GitHub:

```shell
amp install github.com/fastah/ip-geofeed-skills/validator
```

Then invoke it with:

```
/skill validator
```

Or simply ask Amp to validate a geofeed and it will auto-select the skill.

### VS Code / GitHub Copilot

Clone this repository into your workspace, and the skill will be discovered automatically from the `skills/` directory.

## What are Agent Skills

From the [VS Code help page on Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills#_how-copilot-uses-skills):

> Agent Skills standard
Agent Skills is an open standard that enables portability across different AI agents. Skills you create in VS Code work with multiple agents, including:

    GitHub Copilot in VS Code: Available in chat and agent mode
    GitHub Copilot CLI: Accessible when working in the terminal
    GitHub Copilot coding agent: Used during automated coding tasks

> Learn more about the Agent Skills standard at agentskills.io.



## Troubleshooting

1. VS Code configuration - Did you turn ON the experimental Agent Skills flag?
    ![image](https://github.com/user-attachments/assets/74ce679b-5bfa-4b92-a1a8-967dfd248ee0)