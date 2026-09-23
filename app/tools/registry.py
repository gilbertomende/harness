"""Central Tool Registry: the enforcement point for tool metadata, roles and effect class (SECURITY.md §4, ADR-005).

Every tool declares an effect class. A tool registered without one is treated as DESTRUCTIVE
(fail closed): admin-only and approval-gated.
"""
import logging
from enum import Enum
from typing import Awaitable, Callable
log = logging.getLogger("tool_registry")

class Effect(str, Enum):
    READ = "READ"                # list/read file, status
    QUERY = "QUERY"              # RAG search, read-only MCP query
    WRITE = "WRITE"              # write/update a file or record
    EXEC = "EXEC"                # shell/Python/build tools (v0.2: application sandbox only)
    DESTRUCTIVE = "DESTRUCTIVE"  # delete, system config, DB mutation, network administration

ELEVATED_EFFECTS = {Effect.DESTRUCTIVE}   # default roles: admin only

class ToolRegistry:
    def __init__(self): self._tools={}
    def register(self,name,description,schema,fn:Callable[...,Awaitable[str]],effect:Effect|None=None,roles=None,source="native"):
        if effect is None:
            log.warning("tool_unclassified name=%s source=%s -> treated as DESTRUCTIVE", name, source)
            effect = Effect.DESTRUCTIVE
        effect = Effect(effect)
        if roles is None: roles = ("admin",) if effect in ELEVATED_EFFECTS else ("admin","user")
        self._tools[name]={"name":name,"description":description,"schema":schema,"fn":fn,"effect":effect,"roles":set(roles),"source":source}
    def unregister_source(self, source):
        names=[n for n,t in self._tools.items() if t["source"]==source]
        for n in names: del self._tools[n]
        return names
    def specs(self, role="user"):
        return [{"type":"function","function":{"name":t["name"],"description":t["description"],"parameters":t["schema"]}}
                for t in self._tools.values() if role in t["roles"]]
    def get(self,name,role="user"):
        if name not in self._tools: raise ValueError(f"Tool not allowed: {name}")
        t=self._tools[name]
        if role not in t["roles"]: raise PermissionError("Role cannot execute tool")
        return t
    def effect(self,name): return self._tools[name]["effect"] if name in self._tools else Effect.DESTRUCTIVE
    def requires_approval(self,name,approval_effects):
        return self.effect(name) in approval_effects
    async def execute(self,name,args,role="user",approved=False,approval_effects=frozenset({Effect.WRITE,Effect.DESTRUCTIVE})):
        t=self.get(name,role)
        if t["effect"] in approval_effects and not approved: return "APPROVAL_REQUIRED"
        if not isinstance(args,dict): raise ValueError("Tool arguments must be a JSON object")
        return await t["fn"](**args)
registry=ToolRegistry()
