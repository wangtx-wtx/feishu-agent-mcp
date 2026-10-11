import asyncio,contextlib,secrets,json,sys,pathlib
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from .config import Config
from .store import Store
from .feishu import Feishu
from .bridge import Bridge

def app(config,config_path=None,connect=True):
    store=Store(config.state_dir);f=Feishu(config,store);bridge=Bridge(config,store,f)
    mcp=FastMCP('Feishu Agent',stateless_http=True,json_response=True,streamable_http_path='/')
    @mcp.tool()
    async def send_message(text:str,request_id:str|None=None)->dict:
        """Send text to the paired Feishu user. Use a stable request_id for retries."""
        return await f.message(text,request_id)
    @mcp.tool()
    async def send_file(path:str,request_id:str|None=None)->dict:
        """Send a local file under configured allowed roots to the paired user."""
        return await f.file(path,request_id)
    mcp_app=mcp.streamable_http_app()
    process=None;connector_task=None
    async def receive_connector():
        nonlocal process
        process=await asyncio.create_subprocess_exec(sys.executable,'-X','utf8','-u','-m','feishu_agent.connector',str(config_path) if config_path else str(pathlib.Path.home()/'.feishu-agent/config.json'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=4*1024*1024)
        while line:=await process.stdout.readline():
            try:d=json.loads(line)
            except ValueError:continue
            store.event('inbound_received',{'event_id':d.get('header',{}).get('event_id')})
            await bridge.receive(d.get('event',{}))
        store.event('connector_stopped',{'exit_code':await process.wait()})

    @contextlib.asynccontextmanager
    async def lifespan(app):
        nonlocal connector_task
        # OS lock rejects a second owner even if the previous process crashed.
        lockfile=open(pathlib.Path(config.state_dir)/'service.lock','a+b')
        if sys.platform=='win32':
            import msvcrt
            lockfile.seek(0);lockfile.write(b'0');lockfile.flush();lockfile.seek(0);msvcrt.locking(lockfile.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store.recover()
        worker=asyncio.create_task(bridge.worker())
        if connect:connector_task=asyncio.create_task(receive_connector())
        try:
            async with mcp.session_manager.run():yield
        finally:
            worker.cancel()
            if connector_task:connector_task.cancel()
            await asyncio.gather(worker,*([connector_task] if connector_task else []),return_exceptions=True)
            if process and process.returncode is None:process.terminate();await process.wait()
            await bridge.adapter.close();await f.close();lockfile.close()
    application=FastAPI(lifespan=lifespan)
    application.state.bridge=bridge;application.state.store=store;application.state.feishu=f
    @application.middleware('http')
    async def auth(request,call_next):
        if request.headers.get('origin') and request.headers['origin'] not in (f'http://127.0.0.1:{config.port}',f'http://localhost:{config.port}'):
            return JSONResponse({'error':'ORIGIN_DENIED'},403)
        if not secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+config.token):return JSONResponse({'error':'UNAUTHORIZED'},401)
        try:return await call_next(request)
        except ValueError as e:return JSONResponse({'error':str(e)},409)
        except Exception:return JSONResponse({'error':'DELIVERY_OR_SERVICE_ERROR'},502)
    @application.get('/health')
    async def health():return {'running':True,'paired':bool(store.get('owner',config.owner_open_id)),'connector_running':bool(process and process.returncode is None),'agent_configured':bool(config.adapter_command)}
    @application.post('/send_message')
    async def message(request:Request):
        d=await request.json();return await send_message(**d)
    @application.post('/send_file')
    async def file(request:Request):
        d=await request.json();return await send_file(**d)
    application.mount('/mcp',mcp_app)
    return application
