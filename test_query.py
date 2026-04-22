import asyncio
import sys
sys.path.insert(0, 'backend')
from api.routes import router, get_agent
import json

async def test_customer_query():
    # Manually call the endpoint function
    from pydantic import BaseModel
    class CustomerQueryRequest(BaseModel):
        phone: str
    
    request = CustomerQueryRequest(phone="15300000574")
    agent = get_agent()
    result = await agent.api_client.query_customer(request.phone)
    print("Query result:", json.dumps(result, indent=2)[:500])

asyncio.run(test_customer_query())