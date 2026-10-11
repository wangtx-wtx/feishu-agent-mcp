"""The Feishu SDK owns its event loop in this isolated process."""
import sys,json
import lark_oapi as lark
from .config import Config

def main():
    config=Config.load(sys.argv[1] if len(sys.argv)>1 else None)
    def receive(data):
        value=json.loads(lark.JSON.marshal(data))
        sys.stdout.write(json.dumps(value,ensure_ascii=False)+'\n');sys.stdout.flush()
    dispatcher=lark.EventDispatcherHandler.builder('','').register_p2_im_message_receive_v1(receive).build()
    client=lark.ws.Client(config.app_id,config.app_secret,event_handler=dispatcher,log_level=lark.LogLevel.ERROR,domain=config.api_base)
    client.start()

if __name__=='__main__':main()
