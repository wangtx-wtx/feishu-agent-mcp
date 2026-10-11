import pytest,httpx
from feishu_agent.config import Config
from feishu_agent.store import Store
from feishu_agent.feishu import Feishu
from feishu_agent.stream import StreamCard

def test_file_boundary(tmp_path):
    root=tmp_path/'allowed';root.mkdir();good=root/'中文.txt';good.write_text('test')
    c=Config(allowed_roots=[str(root)])
    assert c.file_bytes(good)[1]==b'test'
    outside=tmp_path/'private.txt';outside.write_text('private')
    with pytest.raises(ValueError,match='OUTSIDE'):c.file_bytes(outside)

def test_delivery_uncertainty_and_conflict(tmp_path):
    s=Store(tmp_path);assert s.reserve('key','a') is None
    with pytest.raises(ValueError,match='UNCERTAIN'):s.reserve('key','a')
    with pytest.raises(ValueError,match='CONFLICT'):s.reserve('key','b')
    s.delivered('key',{'message_id':'one'});assert s.reserve('key','a')=={'message_id':'one'}

def test_second_store_does_not_interrupt_active_task(tmp_path):
    s=Store(tmp_path);assert s.enqueue('m',{'text':'hello'});s.claim()
    second=Store(tmp_path)
    assert second.db.execute('select state from inbox').fetchone()[0]=='running'
    second.recover();assert s.db.execute('select state from inbox').fetchone()[0]=='interrupted'
    assert not s.enqueue('m',{'text':'hello'})

def test_control_message_never_becomes_agent_prompt(tmp_path):
    s=Store(tmp_path);s.enqueue('stop',{},state='control');assert s.claim() is None

@pytest.mark.asyncio
async def test_duplicate_send_and_changed_content(tmp_path):
    s=Store(tmp_path);s.set('owner','test-owner');calls=[]
    def handle(r):
        calls.append(r.url.path)
        if '/auth/' in r.url.path:return httpx.Response(200,json={'code':0,'tenant_access_token':'test','expire':7200})
        return httpx.Response(200,json={'code':0,'data':{'message_id':'m1'}})
    f=Feishu(Config(),s);await f.client.aclose();f.client=httpx.AsyncClient(base_url='https://test.invalid',transport=httpx.MockTransport(handle))
    try:
        one=await f.message('hello','same');assert await f.message('hello','same')==one
        with pytest.raises(ValueError,match='CONFLICT'):await f.message('changed','same')
        assert calls.count('/open-apis/im/v1/messages')==1
    finally:await f.close()

@pytest.mark.asyncio
async def test_true_element_stream_and_hidden_reasoning_ignored():
    class F:
        def __init__(self):self.calls=[]
        async def api(self,method,path,**kwargs):self.calls.append((path,kwargs['json']));return {'card_id':'c'}
        async def deliver(self,*args):return {}
        async def message(self,*args):return {}
    f=F();c=StreamCard(f,'r',interval=0);await c.open()
    await c.event({'type':'reasoning_delta','text':'hidden'})
    await c.event({'type':'answer_delta','text':'hello'})
    assert c.summary=='' and c.text=='hello'
    assert f.calls[-1][0].endswith('/elements/answer/content')
    assert f.calls[-1][1]['content']=='hello'
    await c.finish();assert 'hidden' not in str(f.calls)
