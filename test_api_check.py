import asyncio
import sys
sys.path.insert(0, 'backend')
from services.crm_api import CRMAPIClient

async def test():
    client = CRMAPIClient('http://localhost:8000')
    
    # 测试获取主销售品
    print("=== Testing get_order_offers ===")
    result = await client.get_order_offers('120000')
    print('Code:', result.get('code'))
    offers = result.get('resultObj', {}).get('list', [])
    print('Count:', len(offers))
    if offers:
        print('First offer keys:', offers[0].keys())
        print('First offer:', offers[0])
    
    # 测试获取附属销售品
    if offers:
        print("\n=== Testing query_optgroup_offers ===")
        offer_id = str(offers[0].get('prodOfferId', ''))
        opt_result = await client.query_optgroup_offers(offer_id)
        print('Code:', opt_result.get('code'))
        opt_groups = opt_result.get('resultObj', [])
        print('Count:', len(opt_groups))
        if opt_groups:
            print('First group:', opt_groups[0])

asyncio.run(test())