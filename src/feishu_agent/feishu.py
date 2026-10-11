import httpx,time,json,hashlib,uuid,asyncio,mimetypes

class Feishu:
    def __init__(self,config,store):
        self.config=config;self.store=store;self.client=httpx.AsyncClient(base_url=config.api_base,timeout=60)
        self._token='';self._expiry=0;self._token_lock=asyncio.Lock()

    async def token(self):
        async with self._token_lock:
            if time.time()<self._expiry:return self._token
            r=await self.client.post('/open-apis/auth/v3/tenant_access_token/internal',json={'app_id':self.config.app_id,'app_secret':self.config.app_secret})
            r.raise_for_status();d=r.json()
            if d.get('code',0):raise ValueError('FEISHU_AUTH_'+str(d['code']))
            self._token=d['tenant_access_token'];self._expiry=time.time()+d.get('expire',7200)-120
            return self._token

    async def api(self,method,path,**kwargs):
        r=await self.client.request(method,'/open-apis/'+path,headers={'Authorization':'Bearer '+await self.token()},**kwargs)
        r.raise_for_status();d=r.json()
        if d.get('code',0):raise ValueError('FEISHU_API_'+str(d['code']))
        return d.get('data',d)

    async def message(self,text,request_id=None):
        if not text or not text.strip():raise ValueError('MESSAGE_EMPTY')
        if len(text.encode())>28000:raise ValueError('MESSAGE_TOO_LARGE')
        return await self.deliver('text',{'text':text},request_id or uuid.uuid4().hex)

    async def deliver(self,kind,content,key,file=None):
        owner=self.store.get('owner',self.config.owner_open_id)
        if not owner:raise ValueError('OWNER_NOT_PAIRED')
        fingerprint=hashlib.sha256(json.dumps([owner,kind,content,file[1].hex() if file else None],sort_keys=True).encode()).hexdigest()
        previous=self.store.reserve(key,fingerprint)
        if previous:return previous
        if file:
            path,data=file
            uploaded=await self.api('POST','im/v1/files',data={'file_type':'pdf' if path.suffix.lower()=='.pdf' else 'stream','file_name':path.name},files={'file':(path.name,data,mimetypes.guess_type(path.name)[0] or 'application/octet-stream')})
            content={'file_key':uploaded['file_key']}
        result=await self.api('POST','im/v1/messages?receive_id_type=open_id',json={'receive_id':owner,'msg_type':kind,'content':json.dumps(content,ensure_ascii=False),'uuid':hashlib.sha256(key.encode()).hexdigest()[:32]})
        receipt={'status':'sent','message_id':result['message_id']}
        if file:receipt['sha256']=hashlib.sha256(file[1]).hexdigest()
        self.store.delivered(key,receipt);return receipt

    async def file(self,path,request_id=None):
        p,data=self.config.file_bytes(path)
        return await self.deliver('file',{},request_id or uuid.uuid4().hex,file=(p,data))

    async def download(self,message_id,key,type='file'):
        # Every attachment must originate in an accepted owner message.
        async with self.client.stream('GET','/open-apis/im/v1/messages/'+message_id+'/resources/'+key,params={'type':type},headers={'Authorization':'Bearer '+await self.token()}) as r:
            r.raise_for_status();content=bytearray()
            if 'application/json' in r.headers.get('content-type',''):raise ValueError('ATTACHMENT_API_ERROR')
            async for chunk in r.aiter_bytes():
                content.extend(chunk)
                if len(content)>30*1024*1024:raise ValueError('ATTACHMENT_TOO_LARGE')
            return bytes(content)

    async def close(self):await self.client.aclose()
