import sys
sys.path.insert(0, 'backend')
from services.i18n import TRANSLATIONS
import json

# Test encoding to JSON
result = {
    'login_success': TRANSLATIONS['zh']['login_success'],
    'dear_user': TRANSLATIONS['zh']['dear_user'],
}

json_str = json.dumps(result, ensure_ascii=False)
print('JSON:', json_str)

# Check bytes
for key in ['login_success', 'dear_user']:
    val = TRANSLATIONS['zh'][key]
    print(f'{key} bytes:', val.encode('utf-8').hex())