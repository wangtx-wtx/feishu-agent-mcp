import json,time

def card(text,summary='',streaming=True,status='生成中'):
    elements=[]
    if summary or streaming:
        elements.append({'tag':'collapsible_panel','expanded':False,'header':{'title':{'tag':'plain_text','content':'处理摘要 / Processing summary'}},'elements':[{'tag':'markdown','content':summary or '…','element_id':'summary'}]})
    elements.append({'tag':'markdown','content':text or '…','element_id':'answer'})
    return {'schema':'2.0','config':{'streaming_mode':streaming,'update_multi':True},'header':{'title':{'tag':'plain_text','content':status}},'body':{'elements':elements}}

class StreamCard:
    def __init__(self,feishu,request_id,interval=.7):
        self.f=feishu;self.request_id=request_id;self.interval=interval;self.text='';self.summary='';self.card_id=None;self.sequence=0;self.last={};self.failed=False

    async def open(self):
        try:
            d=await self.f.api('POST','cardkit/v1/cards',json={'type':'card_json','data':json.dumps(card(''),ensure_ascii=False)})
            self.card_id=d['card_id']
            await self.f.deliver('interactive',{'type':'card','data':{'card_id':self.card_id}},self.request_id+':card')
        except Exception:
            self.failed=True
            await self.f.message('已收到，正在处理。实时卡片暂不可用，完成后发送结果。',self.request_id+':ack')

    async def event(self,e):
        # Only public_summary events are eligible. Raw reasoning is not rendered.
        if e['type']=='answer_delta':self.text+=e.get('text','')
        elif e['type']=='public_summary_delta':self.summary+=e.get('text','')
        elif e['type']=='answer_replace':self.text=e.get('text','')
        else:return
        element='summary' if e['type']=='public_summary_delta' else 'answer'
        if self.card_id and not self.failed and time.monotonic()-self.last.get(element,0)>=self.interval:
            self.last[element]=time.monotonic();self.sequence+=1
            try:
                content=self.summary if element=='summary' else self.text
                if content:
                    await self.f.api('PUT',f'cardkit/v1/cards/{self.card_id}/elements/{element}/content',json={'content':content,'sequence':self.sequence,'uuid':self.request_id+':'+str(self.sequence)})
                    if hasattr(self.f,'store'):self.f.store.event('card_stream_update',{'request':self.request_id,'element':element,'chars':len(content)})
            except Exception:self.failed=True

    async def finish(self,status='完成'):
        if self.card_id and not self.failed:
            self.sequence+=1
            try:
                await self.f.api('PUT','cardkit/v1/cards/'+self.card_id,json={'card':{'type':'card_json','data':json.dumps(card(self.text,self.summary,False,status),ensure_ascii=False)},'sequence':self.sequence,'uuid':self.request_id+':final'})
                return
            except Exception:self.failed=True
        text=self.text or status
        for index,start in enumerate(range(0,len(text),6000)):await self.f.message(text[start:start+6000],self.request_id+':final:'+str(index))
