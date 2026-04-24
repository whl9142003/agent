import sys
sys.path.insert(0, 'backend')
from services.i18n import format_offers_for_language
import json

offers = [
    {
        'offerName': '5G套餐128元',
        'effDate': '2024-01-01 00:00:00',
        'expDate': '2099-12-31 23:59:59',
        'subscribeDate': '2024-01-01 10:30:00',
        'productOfferType': '6',
        'subOfferInst': [
            {'offerName': '语音分钟数', 'billingNo': '13800138001', 'contractCd': 'CT001', 'effDate': '2024-01-01 00:00:00', 'expDate': '2099-12-31 23:59:59'},
            {'offerName': '流量包', 'billingNo': '13800138001', 'effDate': '2024-01-01 00:00:00', 'expDate': '2099-12-31 23:59:59'}
        ]
    }
]

result = format_offers_for_language(offers, 'zh')

# Save to file for inspection
with open('test_output.txt', 'w', encoding='utf-8') as f:
    f.write(result)

print('Output saved to test_output.txt')
print('First 100 chars:', result[:100])