"""One-time script: split tools.py into categorized sub-modules + helpers."""
from pathlib import Path

TOOLS_PY = Path(r"\\wsl.localhost\Ubuntu\home\rausraus\Code\MemoryMCP\memory_mcp\api\mcp\tools.py")
MCP_DIR = TOOLS_PY.parent

COMMON_IMPORTS = [
    "from __future__ import annotations\n\n",
    "import json\n",
    "import logging\n",
    "from typing import TYPE_CHECKING, Any\n\n",
    "from mcp.server.fastmcp import FastMCP  # noqa: TC002\n\n",
    "from memory_mcp.api.mcp.middleware import get_current_persona\n",
    "from memory_mcp.application.use_cases import AppContextRegistry\n",
    "from memory_mcp.domain.search.engine import SearchQuery\n",
    "from memory_mcp.domain.shared.time_utils import get_now, relative_time_str\n\n",
    "logger = logging.getLogger(__name__)\n\n",
    "if TYPE_CHECKING:\n",
    "    from memory_mcp.application.use_cases import AppContext\n",
    "    from memory_mcp.domain.persona.entities import PersonaState\n\n\n",
]

# (start_line_1idx, end_line_1idx) for each group
GROUPS = {
    "_tools_memory.py": [
        (156, 201), (204, 276), (279, 324),
        (327, 365), (368, 443), (446, 472),
    ],
    "_tools_persona.py": [
        (53, 153), (475, 613),
    ],
    "_tools_item.py": [
        (616, 650), (653, 679), (682, 708), (711, 738),
        (741, 784), (787, 827), (830, 871),
    ],
    "_tools_sandbox.py": [
        (874, 929), (932, 1138),
    ],
    "_tools_goal.py": [
        (1141, 1273), (1276, 1408),
    ],
    "_tools_skill.py": [
        (1411, 1513),
    ],
    # Helpers referenced by _tool_get_context (moved to shared module)
    "_tools_helpers.py": [
        (1865, 1898),   # _format_state_block
        (1901, 1914),   # _format_state_diff
        (1921, 1935),   # _parse_days_from_relative
        (1938, 1946),   # _build_time_comment
        (1949, 2107),   # _format_lightweight_response
    ],
}

with open(TOOLS_PY, encoding="utf-8") as f:
    lines = f.readlines()

# 1. Create sub-modules
for filename, ranges in GROUPS.items():
    out_path = MCP_DIR / filename
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f'"""Auto-generated from tools.py split — {filename}."""\n')
        if filename == "_tools_helpers.py":
            # Helpers don't need MCP-specific imports
            f.write("from __future__ import annotations\n\n")
            f.write("from typing import TYPE_CHECKING\n\n")
            f.write("from memory_mcp.domain.shared.time_utils import relative_time_str\n\n")
            f.write("if TYPE_CHECKING:\n")
            f.write("    from memory_mcp.domain.persona.entities import PersonaState\n\n\n")
        else:
            f.writelines(COMMON_IMPORTS)
            # Persona module also needs helpers
            if filename == "_tools_persona.py":
                f.write("from memory_mcp.api.mcp._tools_helpers import _format_lightweight_response  # noqa: E402\n\n")

        for start, end in ranges:
            block_lines = [lines[i] for i in range(start - 1, end)]
            if block_lines and block_lines[-1].strip():
                block_lines.append("\n")
            f.writelines(block_lines)
            f.write("\n")
    lc = len(open(out_path, encoding="utf-8").readlines())
    print(f"Created {out_path.name}: {lc} lines")

# 2. Rebuild tools.py: keep lines 0-51 (imports + _VALID_EMOTIONS),
#    remove all lines 52-2107 (functions we extracted except _resolve_persona line 1917-1918),
#    add sub-module imports, keep TOOL_DISPATCH + register_tools wrappers + _resolve_persona

new_lines = list(lines[:51])  # lines 0-50
new_lines.append("\n")

# Import all _tool_* functions from sub-modules
imports_block = [
    "# ── Re-export core implementations from sub-modules ──\n",
    "from memory_mcp.api.mcp._tools_helpers import (  # noqa: E402, F401\n",
    "    _format_lightweight_response,\n",
    "    _format_state_block,\n",
    "    _format_state_diff,\n",
    "    _parse_days_from_relative,\n",
    "    _build_time_comment,\n",
    ")\n",
    "from memory_mcp.api.mcp._tools_memory import (  # noqa: E402, F401\n",
    "    _tool_memory_create,\n",
    "    _tool_memory_read,\n",
    "    _tool_memory_update,\n",
    "    _tool_memory_delete,\n",
    "    _tool_memory_search,\n",
    "    _tool_memory_stats,\n",
    ")\n",
    "from memory_mcp.api.mcp._tools_persona import _tool_get_context, _tool_update_context  # noqa: E402, F401\n",
    "from memory_mcp.api.mcp._tools_item import (  # noqa: E402, F401\n",
    "    _tool_item_add,\n",
    "    _tool_item_remove,\n",
    "    _tool_item_equip,\n",
    "    _tool_item_unequip,\n",
    "    _tool_item_update,\n",
    "    _tool_item_search,\n",
    "    _tool_item_history,\n",
    ")\n",
    "from memory_mcp.api.mcp._tools_sandbox import _tool_sandbox, _tool_sandbox_files  # noqa: E402, F401\n",
    "from memory_mcp.api.mcp._tools_goal import _tool_goal_manage, _tool_promise_manage  # noqa: E402, F401\n",
    "from memory_mcp.api.mcp._tools_skill import _tool_invoke_skill  # noqa: E402, F401\n",
    "\n",
]
new_lines.extend(imports_block)

# Keep TOOL_DISPATCH (lines 1514-1541 0-idx)
new_lines.extend(lines[1514:1542])
new_lines.append("\n")

# Keep section header + register_tools + wrappers (lines 1543-1858 0-idx)
new_lines.extend(lines[1543:1859])
new_lines.append("\n")

# Add _resolve_persona (must stay in tools.py for wrappers)
new_lines.extend(lines[1916:1919])  # just the function + blank line

with open(TOOLS_PY, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"\nUpdated tools.py: {len(new_lines)} lines")
print("Split complete!")
