# Hogar de los Alpes — Claude Code

Ver **`AGENTS.md`** primero — es la guía de orientación del proyecto, escrita para cualquier
asistente de IA (Claude Code, Gemini CLI, Codex CLI, u otro) que abra este repo. Aplica igual aquí;
no la dupliques ni la reescribas en este archivo.

## Específico de Claude Code

Los 6 roles de equipo descritos en `AGENTS.md` están disponibles como **subagentes nativos** en
`.claude/agents/*.md` — invócalos con la herramienta `Agent`, pasando `subagent_type` igual al
nombre del archivo (sin extensión), por ejemplo `subagent_type: "rubrica-auditor"`.
