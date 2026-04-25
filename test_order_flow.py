import sys
sys.path.insert(0, 'backend')
import asyncio
from services.crm_agent import CRMAgent
from services.llm_factory import create_llm
from services.crm_agent import CRMAPIClient
import config

async def test():
    api_client = CRMAPIClient(config.CRM_API_BASE_URL)
    llm = create_llm('deepseek')
    agent = CRMAgent(api_client, llm)

    # 登录
    r1 = await agent.process_message('test1', '13800138000 123456')
    print('1. Login:', r1.get('type'))

    # 说要办理业务
    r2 = await agent.process_message('test1', '我要办理套餐')
    print('2. Order offer:', r2.get('type'))
    print('   Offers count:', len(r2.get('offers', [])))

    # 输入套餐名称
    r3 = await agent.process_message('test1', '5G Smart Offer')
    print('3. Select offer:', r3.get('type'))
    print('   Msg:', r3.get('message', '')[:100] if r3.get('message') else 'None')

asyncio.run(test())