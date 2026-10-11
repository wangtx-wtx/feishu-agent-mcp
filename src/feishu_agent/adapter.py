"""Portable NDJSON adapter protocol; never execute shell command strings."""
import asyncio,json,os,uuid

class Adapter:
    def __init__(self,config):
        self.config=config;self.proc=None;self.pending={};self.events=asyncio.Queue();self.reader=None

    async def start(self):
        if self.proc and self.proc.returncode is None:return
        if not self.config.adapter_command:raise ValueError('ADAPTER_NOT_CONFIGURED')
        self.proc=await asyncio.create_subprocess_exec(*self.config.adapter_command,cwd=self.config.adapter_cwd or None,env={**os.environ,**self.config.adapter_env},stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=4*1024*1024)
        self.reader=asyncio.create_task(self._read())
        await self.request('initialize',{})

    async def _read(self):
        try:
            while line:=await self.proc.stdout.readline():
                d=json.loads(line)
                if 'id' in d and d['id'] in self.pending:
                    future=self.pending.pop(d['id'])
                    if d.get('error'):future.set_exception(ValueError('ADAPTER_'+str(d['error'].get('message','ERROR'))))
                    else:future.set_result(d.get('result',{}))
                elif d.get('method')=='agent.event':await self.events.put(d['params'])
        finally:
            for future in self.pending.values():
                if not future.done():future.set_exception(ValueError('ADAPTER_DISCONNECTED'))
            self.pending.clear();await self.events.put({'type':'error','text':'ADAPTER_DISCONNECTED'})

    async def request(self,method,params):
        id=uuid.uuid4().hex;future=asyncio.get_running_loop().create_future();self.pending[id]=future
        self.proc.stdin.write((json.dumps({'jsonrpc':'2.0','id':id,'method':method,'params':params},ensure_ascii=False)+'\n').encode());await self.proc.stdin.drain()
        try:return await asyncio.wait_for(future,90)
        finally:self.pending.pop(id,None)

    async def run(self,session,text,attachments=None):
        await self.start()
        while not self.events.empty():self.events.get_nowait()
        await self.request('prompt',{'session_id':session,'text':text,'attachments':attachments or []})
        while True:
            e=await asyncio.wait_for(self.events.get(),1800)
            if e.get('session_id') not in (None,session):continue
            yield e
            if e['type'] in ('done','error','cancelled'):break

    async def cancel(self,session):
        if self.proc and self.proc.returncode is None:return await self.request('cancel',{'session_id':session})
        return {'cancelled':False}

    async def close(self):
        if not self.proc or self.proc.returncode is not None:return
        try:await self.request('shutdown',{})
        except Exception:pass
        try:await asyncio.wait_for(self.proc.wait(),8)
        except asyncio.TimeoutError:self.proc.terminate();await self.proc.wait()
        if self.reader:self.reader.cancel()
