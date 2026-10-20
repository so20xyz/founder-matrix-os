<sub>**📅 Star counts last verified: 2026-10-20**</sub>

---

## 🧪 Autonomous Research Systems

> Multi-stage systems that autonomously handle several parts of the research loop, such as hypothesis generation, experimentation, analysis, and manuscript preparation.

| Project & Stars | Description | Framework & LLM APIs |
|---|---|---|
| [autoresearch](https://github.com/karpathy/autoresearch)<br><img src="https://img.shields.io/github/stars/karpathy/autoresearch?style=flat" alt="GitHub stars" height="20"> | By Andrej Karpathy. A minimal single-GPU research harness where an external coding agent repeatedly edits `train.py` and runs fixed five-minute nanochat experiments under instructions in `program.md`. | <b>Tools:</b> Custom (PyTorch, nanochat)<br><b>LLM APIs:</b> External coding agents such as Anthropic Claude Code and OpenAI Codex |
| [RD-Agent](https://github.com/microsoft/RD-Agent)<br><img src="https://img.shields.io/github/stars/microsoft/RD-Agent?style=flat" alt="GitHub stars" height="20"> | Microsoft. Research and development agents for data science, quant factor/model evolution, Kaggle automation, paper-to-code implementation, and LLM fine-tuning. | <b>Tools:</b> Custom + **LiteLLM**, Docker, Qlib<br><b>LLM APIs:</b> OpenAI, Azure OpenAI, DeepSeek; LiteLLM-supported providers |
| [claude-scholar](https://github.com/Galaxy-Dawn/claude-scholar)<br><img src="https://img.shields.io/github/stars/Galaxy-Dawn/claude-scholar?style=flat" alt="GitHub stars" height="20"> | Semi-automated academic research assistant covering literature review, coding, experiments, writing, publication, and project knowledge management, with separate coding-agent branches. | <b>Tools:</b> **Claude Code** / Codex CLI / Kimi Code CLI / OpenCode, Zotero MCP, Obsidian, LaTeX<br><b>LLM APIs:</b> Anthropic Claude, OpenAI (Codex), Moonshot Kimi; OpenCode-configured providers |

[↑ Back to contents](#-table-of-contents)

## ⚙️ Research Implementation & Experimentation

| Project & Stars | Description | Framework & LLM APIs |
|---|---|---|
| [AIDE](https://github.com/WecoAI/aideml)<br><img src="https://img.shields.io/github/stars/WecoAI/aideml?style=flat" alt="GitHub stars" height="20"> | Open-source reference implementation of AIDE. Searches a tree of candidate ML programs, using execution results and a user-defined metric to guide drafting, debugging, and improvement. [[paper]](https://arxiv.org/abs/2502.13138) | <b>Tools:</b> Agentic tree search, Python CLI, Streamlit, Docker<br><b>LLM APIs:</b> OpenAI, Anthropic, Gemini; OpenAI-compatible local models such as Ollama |
| [Paper2Agent](https://github.com/jmiao24/Paper2Agent)<br><img src="https://img.shields.io/github/stars/jmiao24/Paper2Agent?style=flat" alt="GitHub stars" height="20"> | Turns research papers and their codebases into MCP servers and reusable skills, exposing scientific methods, data, and workflows as callable tools. | <b>Tools:</b> Agent Skills, parallel specialist agents, MCP, paper / codebase analysis<br><b>LLM APIs:</b> Agent-dependent: Claude Code, Codex, and other skill-compatible coding agents |

## 📋 Awesome Lists & Surveys

| Project & Stars | Description |
|---|---|
| [awesome-autoresearch](https://github.com/webfuse-com/awesome-autoresearch)<br><img src="https://img.shields.io/github/stars/webfuse-com/awesome-autoresearch?style=flat" alt="GitHub stars" height="20"> | Curated index of autonomous improvement loops and research agents inspired by Karpathy's autoresearch, including platform ports, domain adaptations, evaluations, and case studies. |

## 💡 How This Differs from General AI Agent Lists

General-purpose coding agents (OpenHands, Aider, SWE-agent) are included.
