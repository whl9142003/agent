import asyncio
import sys
sys.path.insert(0, 'backend')

from services.crm_agent import CRMAPIClient, CRMAgent
from services.llm_factory import create_llm
import config

async def test_login():
    print("[TEST] Starting login test")
    client = CRMAPIClient(base_url=config.CRM_API_BASE_URL)
    llm = create_llm()
    agent = CRMAgent(client, llm)

    message = "15300000574 password"
    result = await agent.process_message("test_session", message)

    print("[TEST] Result:", result)
    return result

result = asyncio.run(test_login())