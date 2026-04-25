import sys
sys.path.insert(0, 'backend')
import asyncio
import traceback

from services.crm_agent import CRMAgent
from services.llm_factory import create_llm
from services.crm_agent import CRMAPIClient
import config

async def test_order():
    api_client = CRMAPIClient(config.CRM_API_BASE_URL)
    llm_service = create_llm('deepseek')
    agent = CRMAgent(api_client, llm_service)

    # Login first
    result1 = await agent.process_message('debug_test', '13800138000 123456')
    print('1. Login:', result1.get('type'))

    # Test ordering intent
    try:
        result2 = await agent.process_message('debug_test', '要办理套餐')
        print('2. Order:', result2.get('type'))
        print('   Msg:', result2.get('message', '')[:150] if result2.get('message') else 'None')
    except Exception as e:
        print('Error:', e)
        traceback.print_exc()

asyncio.run(test_order())