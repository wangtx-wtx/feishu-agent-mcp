import asyncio,json,secrets,pathlib,uuid,re
from .adapter import Adapter
from .stream import StreamCard

class Bridge:
    def __init__(self,config,store,feishu,adapter=None):
        self.config=config;self.store=store;self.feishu=feishu;self.adapter=adapter or Adapter(config);self.current=None

    async def receive(self,event):
        sender=event.get('sender',{});m=event.get('message',{})
        if sender.get('sender_type')!='user' or m.get('chat_type')!='p2p':return
        user=sender.get('sender_id',{}).get('open_id');id=m.get('message_id')
        if not id or not user:return
        content=json.loads(m.get('content','{}'));text=content.get('text','')
        owner=self.store.get('owner',self.config.owner_open_id)
        if not owner:
            if not secrets.compare_digest(text.strip(),'/pair '+self.config.pairing_code):return
            if not self.store.enqueue(id,{},state='control'):return
            self.store.set('owner',user);self.store.set('pairing_used',True)
            await self.feishu.message('绑定成功。现在可以与 Agent 对话。',id+':paired');self.store.finish(id);return
        if user!=owner:return
        if text.strip() in ('/stop','停止当前任务'):
            if not self.store.enqueue(id,{},state='control'):return
            result=await self.adapter.cancel(self.store.session())
            await self.feishu.message('已请求停止当前运行。' if result.get('cancelled') else '当前没有可停止的运行。',id+':stop');self.store.finish(id);return
        if not self.store.enqueue(id,{'message':m,'content':content,'text':text}):return

    async def worker(self):
        while True:
            item=self.store.claim()
            if not item:await asyncio.sleep(.2);continue
            id,d=item;self.current=id
            try:
                if d['text'].strip() in ('/new','/clear','清除上下文','清空上下文'):
                    self.store.set('session','feishu-'+uuid.uuid4().hex)
                    await self.feishu.message('已新建聊天上下文，文件和历史记录保留。',id+':new');self.store.finish(id);continue
                files=[];m=d['message'];content=d['content']
                if m['message_type'] in ('file','image'):
                    key=content.get('file_key') or content.get('image_key');data=await self.feishu.download(id,key,'image' if m['message_type']=='image' else 'file')
                    name=re.sub(r'[^\w.\-\u4e00-\u9fff]','_',content.get('file_name') or (key+'.png'))[:150]
                    directory=pathlib.Path(self.config.state_dir)/'attachments'/hash_id(id);directory.mkdir(parents=True,exist_ok=True)
                    path=directory/name;path.write_bytes(data);files.append({'path':str(path),'name':name,'type':m['message_type']})
                sc=StreamCard(self.feishu,id,self.config.stream_interval);await sc.open();status='完成'
                async for e in self.adapter.run(self.store.session(),d['text'] or '请处理我上传的附件。',files):
                    if e['type'] in ('error','cancelled'):status='失败' if e['type']=='error' else '已停止';sc.text+='\n'+e.get('text',status)
                    await sc.event(e)
                    # Record event kind/count only; never persist hidden reasoning.
                    self.store.event('agent_event',{'request':id,'type':e['type'],'chars':len(e.get('text',''))})
                await sc.finish(status);self.store.finish(id,'completed' if status=='完成' else 'failed')
            except Exception as e:
                self.store.finish(id,'failed');self.store.event('request_failed',{'request':id,'code':type(e).__name__})
                try:await self.feishu.message('本次处理未完成：'+(str(e) if isinstance(e,ValueError) else type(e).__name__),id+':error')
                except Exception:pass
            finally:self.current=None

def hash_id(value):
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()[:24]
