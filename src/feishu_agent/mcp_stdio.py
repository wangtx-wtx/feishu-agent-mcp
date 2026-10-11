import httpx
from mcp.server.fastmcp import FastMCP
from .config import Config

def run(config_path=None):
    c=Config.load(config_path);mcp=FastMCP('Feishu Agent')
    async def call(tool,payload):
        async with httpx.AsyncClient(timeout=180) as client:
            r=await client.post(f'http://127.0.0.1:{c.port}/'+tool,headers={'Authorization':'Bearer '+c.token},json=payload)
            if r.is_error:raise ValueError(r.json().get('error','COMMUNICATION_ERROR'))
            return r.json()
    @mcp.tool()
    async def send_message(text:str,request_id:str|None=None)->dict:
        """Send a message to your paired Feishu user. Stable request_id makes retries safe."""
        return await call('send_message',{'text':text,'request_id':request_id})
    @mcp.tool()
    async def send_file(path:str,request_id:str|None=None)->dict:
        """Send a file from an allowed local directory to your paired Feishu user."""
        return await call('send_file',{'path':path,'request_id':request_id})
    mcp.run(transport='stdio')
