from typing import Awaitable, Callable
class ToolRegistry:
    def __init__(self): self._tools={}
    def register(self,name,description,schema,fn:Callable[...,Awaitable[str]],mutating=False,roles=("admin","user")):
        self._tools[name]={"name":name,"description":description,"schema":schema,"fn":fn,"mutating":mutating,"roles":set(roles)}
    def specs(self, role="user"):
        return [{"type":"function","function":{"name":t["name"],"description":t["description"],"parameters":t["schema"]}}
                for t in self._tools.values() if role in t["roles"]]
    def get(self,name,role="user"):
        if name not in self._tools: raise ValueError(f"Tool not allowed: {name}")
        t=self._tools[name]
        if role not in t["roles"]: raise PermissionError("Role cannot execute tool")
        return t
    def is_mutating(self,name): return bool(self._tools.get(name,{}).get("mutating"))
    async def execute(self,name,args,role="user",approved=False):
        t=self.get(name,role)
        if t["mutating"] and not approved: return "APPROVAL_REQUIRED"
        if not isinstance(args,dict): raise ValueError("Tool arguments must be a JSON object")
        return await t["fn"](**args)
registry=ToolRegistry()
