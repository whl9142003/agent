import sys
sys.path.insert(0, 'backend')
import traceback

from services.llm_factory import create_llm
llm = create_llm('deepseek')

intent_prompt = """你是电信营业厅智能客服小信，需要快速判断用户想做什么。

用户说：帮我办理一个套餐
登录状态：已登录
对话历史：无

请快速判断（只回一个词）：
- 推荐套餐：用户问"有什么套餐推荐"、"想换个套餐"、"哪个划算"、"我流量不够用"、"想便宜点"、"家里要宽带"这类
- 办理业务：用户说"要办理"、"帮我开卡"、"加个流量包"、"降套餐"
- 查询订单：用户说"查一下我办的订单"、"订单到哪了"、"我的订单"
- 咨询问题：用户问规则、问费用、问怎么操作等
- 闲聊/其他：问候、闲聊、不会等

只返回一个词（推荐套餐/办理业务/查询订单/咨询问题/其他）："""

try:
    result = llm.invoke(intent_prompt)
    print('Intent:', result.content if hasattr(result, 'content') else result)
except Exception as e:
    print('Error:', e)
    traceback.print_exc()