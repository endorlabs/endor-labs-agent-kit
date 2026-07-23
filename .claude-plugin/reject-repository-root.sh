        #!/usr/bin/env bash
        # endor_agent_kit_managed=true

        event_name="${1:-UserPromptSubmit}"
        cat >/dev/null || true
        message="Endor Labs Agent Kit: the repository root is the Cursor package and is not a supported Claude Code plugin root. Relaunch from the repository root with: claude --plugin-dir plugins/claude/endor-labs-agent-kit"

        if [[ "$event_name" == "UserPromptSubmit" ]]; then
          printf '%s
' "$message" >&2
          exit 2
        fi

        printf '%s
' "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"Endor Labs Agent Kit: the repository root is the Cursor package and is not a supported Claude Code plugin root. Relaunch from the repository root with: claude --plugin-dir plugins/claude/endor-labs-agent-kit\"}}"
        exit 0
