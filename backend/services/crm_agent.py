"""
CRM Agent - 基于 LangChain 简化版架构
使用 LLM + Functions 模式实现对话 + 知识库增强
"""
import json
import re
import httpx
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime

# 知识库
from services.knowledge_base import get_knowledge_base, KnowledgeBase


# ============ CRM API Client ============

class CRMAPIClient:
    """CRM API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url

    async def send_verification_code(self, phone: str) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/api/auth/send-code", json={"phone": phone})
            return response.json()

    async def authenticate(self, phone: str, code: str = None, password: str = None, auth_type: str = "password") -> Dict:
        auth_data = {"phone": phone, "auth_type": auth_type, "password": password}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/api/auth/login", json=auth_data)
                return response.json()
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def get_products(self, keyword: str = None, category: str = None) -> Dict:
        params = {}
        if keyword: params["keyword"] = keyword
        if category: params["category"] = category
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/api/products", params=params)
            return response.json()

    async def get_recommendations(self, customer_id: str) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/api/products/recommend/{customer_id}")
            return response.json()

    async def create_order(self, customer_id: str, product_id: str, product_name: str, price: float) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/api/orders", json={
                "customer_id": customer_id, "product_id": product_id,
                "product_name": product_name, "price": price
            })
            return response.json()

    async def get_orders(self, customer_id: str) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/api/orders/{customer_id}")
            return response.json()

    async def process_payment(self, order_id: str, customer_id: str, payment_method: str = "account_balance") -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/api/payment/pay", json={
                "order_id": order_id, "customer_id": customer_id, "payment_method": payment_method
            })
            return response.json()


# ============ 会话状态管理 (支持上下文记忆) ============

import config

class CRMState:
    def __init__(self):
        self.authenticated = False
        self.customer_id: Optional[str] = None
        self.customer_name: Optional[str] = None
        self.phone: Optional[str] = None
        self.account_balance: float = 0.0
        self.current_package: str = ""
        self.current_order: Optional[Dict] = None
        self.conversation_history: List[Dict] = []
        self.last_topic: Optional[str] = None  # 记录最后的话题
        
        # 会话配置
        self.max_history = config.SESSION_CONFIG.get("max_history", 20)
        self.context_window = config.SESSION_CONFIG.get("context_window", 10)

    def add_message(self, role: str, content: str):
        """添加消息到历史记录"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # 限制历史长度
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def get_conversation_context(self, include_last: int = None) -> str:
        """获取会话上下文"""
        if include_last is None:
            include_last = self.context_window
        recent = self.conversation_history[-include_last:] if self.conversation_history else []
        
        context_parts = []
        for msg in recent:
            role_emoji = "🙋" if msg["role"] == "user" else "🤖"
            context_parts.append(f"{role_emoji} {msg['content']}")
        
        return "\n".join(context_parts)

    def get_user_info(self) -> str:
        """获取用户信息用于上下文"""
        if not self.authenticated:
            return "[用户状态] 未登录"
        return f"[用户状态] 已登录 - 姓名:{self.customer_name}, 套餐:{self.current_package}, 余额:{self.account_balance}元"

    def detect_topic(self, message: str) -> Optional[str]:
        """检测话题变化"""
        message_lower = message.lower()
        
        topics = {
            "product": ["套餐", "产品", "5g", "4g", "流量", "价格", "多少钱"],
            "order": ["订单", "进度", "状态", "查询"],
            "login": ["登录", "登陆", "密码"],
            "payment": ["支付", "付款", "钱"],
            "recommend": ["推荐", "适合"]
        }
        
        for topic, keywords in topics.items():
            if any(kw in message_lower for kw in keywords):
                return topic
        return None

    def set_topic(self, topic: str):
        """设置当前话题"""
        self.last_topic = topic

    def to_dict(self) -> Dict:
        return {
            "authenticated": self.authenticated,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "phone": self.phone,
            "account_balance": self.account_balance,
            "current_package": self.current_package,
            "current_order": self.current_order,
            "conversation_history": self.conversation_history,
            "last_topic": self.last_topic
        }


# ============ LangChain Agent ============

class CRMAgent:
    """基于 LangChain 的 CRM 智能体 - 简化版"""

    def __init__(self, api_client: CRMAPIClient, llm_service):
        self.api_client = api_client
        self.llm_service = llm_service
        self.sessions: Dict[str, CRMState] = {}
        
        # 知识库
        self.knowledge_base = get_knowledge_base()
        
        # 系统提示词
        self.system_prompt = """你是一个专业的电信业务客服助手，帮助用户办理套餐、查询订单等业务。

业务规则：
1. 产品查询和推荐不需要登录，任何用户都可以使用
2. 订购产品、查询订单、支付需要用户先登录
3. 用户说要"登录"时，引导用户输入手机号和密码（格式：手机号 密码）
4. 用户选择订购时，检查是否已登录，未登录提示先登录
5. 使用知识库中的产品信息和状态映射来格式化回复

知识库信息:
- 产品名称: 5G畅享128(128元,30GB流量), 5G畅享198(198元,60GB流量), 5G畅享298(298元,150GB流量)
- 状态映射: pending_payment=待支付, paid=已支付, processing=处理中, completed=已完成, cancelled=已取消

回答要求：
1. 使用中文回复
2. 保持友好、专业
3. 如实传达工具返回的结果
4. 根据用户已登录状态提供个性化服务
"""

    def get_session(self, session_id: str) -> CRMState:
        if session_id not in self.sessions:
            self.sessions[session_id] = CRMState()
        return self.sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def process_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """处理用户消息 - 使用 LangChain LLM，支持上下文记忆"""
        state = self.get_session(session_id)
        
        # 检测并记录话题变化
        detected_topic = state.detect_topic(message)
        if detected_topic and detected_topic != state.last_topic:
            # 话题变化了
            if state.last_topic and detected_topic != state.last_topic:
                pass  # 话题切换
            state.set_topic(detected_topic)
        
        # 添加用户消息到历史记录
        state.add_message("user", message)
        
        # 检查是否是登录消息（手机号+密码格式）
        phone_match = re.search(r"1[3-9]\d{9}", message)
        has_space = " " in message or "," in message
        
        if phone_match and has_space:
            parts = re.split(r"[,\s]+", message)
            phone = phone_match.group()
            password = next((p for p in parts if len(p) >= 6 and not p.isdigit()), None)
            
            if password:
                result = await self.api_client.authenticate(phone, password=password)
                if result.get("success"):
                    customer = result.get("customer", {})
                    state.authenticated = True
                    state.customer_id = customer.get("customer_id")
                    state.customer_name = customer.get("name")
                    state.phone = customer.get("phone")
                    state.account_balance = customer.get("account_balance", 0)
                    state.current_package = customer.get("current_package", "")
                    state.set_topic("login")  # 设置话题为登录
                    
                    success_msg = f"✅ 认证成功！\n\n尊敬的用户 {state.customer_name}，您好！\n您当前使用的是：{state.current_package}\n账户余额：{state.account_balance}元"
                    state.add_message("assistant", success_msg)
                    
                    return {
                        "type": "auth_success",
                        "message": success_msg,
                        "customer": customer
                    }
                else:
                    return {"type": "auth_failed", "message": "登录失败，请检查手机号和密码后重试。"}
        
        # 检查是否需要登录但未登录
        message_lower = message.lower()
        need_auth_keywords = ["订单", "订购", "办理", "支付", "购买", "我要这个"]
        
        if any(kw in message_lower for kw in need_auth_keywords) and not state.authenticated:
            return {
                "type": "auth_required",
                "message": "🔐 该操作需要先登录验证。\n\n请输入手机号和密码"
            }
        
        # 使用 LLM 生成回复（含上下文记忆）
        try:
            # 构建上下文信息
            user_info = state.get_user_info()
            conversation_context = state.get_conversation_context()
            
            # 构建完整的上下文提示
            context_prompt = f"""当前会话上下文：
{conversation_context}

{user_info}

当前话题: {state.last_topic or '无'}

用户新消息: {message}

请根据上下文历史和当前话题回复用户，保持对话连贯性。如果用户切回之前的话题，需要结合历史对话内容回复。"""
            
            # 根据意图调用不同处理
            response_msg = ""
            response_type = "text"
            
            if "产品" in message_lower or "套餐" in message_lower or "5g" in message_lower or "4g" in message_lower:
                result = await self.api_client.get_products(keyword="5G" if "5g" in message_lower else None)
                if result.get("success"):
                    products = result.get("products", [])
                    # 使用知识库格式化产品信息
                    formatted_products = self.knowledge_base.format_product(products)
                    response_msg = "为您找到以下产品：\n\n" + "\n".join([
                        f"📦 {p['name']}\n   价格：{p.get('price', 'N/A')}元/月\n   包含：{p.get('data_quota', 'N/A')}流量 + {p.get('voice_quota', 'N/A')}通话\n   适合：{p.get('description', 'N/A')}"
                        for p in formatted_products
                    ])
                else:
                    response_msg = "抱歉，未找到相关产品。"
                    
            elif "推荐" in message_lower:
                if state.authenticated:
                    result = await self.api_client.get_recommendations(state.customer_id)
                    if result.get("success"):
                        recs = result.get("recommendations", [])
                        response_msg = "📊 为您推荐：\n\n" + "\n".join([
                            f"📦 {p['name']} - {p['price']}元/月"
                            for p in recs
                        ])
                    else:
                        response_msg = "暂无推荐。"
                else:
                    result = await self.api_client.get_products(keyword="5G")
                    if result.get("success"):
                        products = result.get("products", [])[:3]
                        response_msg = "📊 为您推荐热门产品：\n\n" + "\n".join([
                            f"📦 {p['name']} - {p['price']}元/月"
                            for p in products
                        ])
                        
            elif "订单" in message_lower:
                if state.authenticated:
                    result = await self.api_client.get_orders(state.customer_id)
                    if result.get("success"):
                        orders = result.get("orders", [])
                        # 使用知识库映射状态
                        formatted_orders = self.knowledge_base.map_status(orders)
                        response_msg = "📋 您的订单列表：\n\n" + "\n".join([
                            f"📋 {o['product_name']}\n   状态：{o.get('status_text', o.get('status', 'N/A'))}"
                            for o in formatted_orders
                        ]) if orders else "您暂无订单记录。"
                    else:
                        response_msg = "查询失败，请稍后重试。"
                else:
                    response_msg = "🔐 查询订单需要先登录。请输入手机号和密码"
                    
            elif "订购" in message_lower:
                if not state.authenticated:
                    return {"type": "auth_required", "message": "🔐 订购需要先登录。请输入手机号和密码"}
                # 需要产品信息才能创建订单，这里返回指引
                response_msg = "好的，您想订购产品。请告诉我想订购哪个产品？输入产品名称或说'推荐'获取推荐。"
                
            elif "支付" in message_lower:
                if state.authenticated and state.current_order:
                    result = await self.api_client.process_payment(state.current_order["order_id"], state.customer_id)
                    if result.get("success"):
                        response_msg = "✅ 支付成功！"
                    else:
                        response_msg = f"支付失败：{result.get('message', '未知错误')}"
                else:
                    response_msg = "您当前没有待支付订单。"
                    
            elif "login" in message_lower or "登录" in message_lower:
                response_msg = "🔐 请输入手机号和密码完成登录（格式：手机号 密码）"
                state.set_topic("login")
                
            elif "menu" in message_lower or any(kw in message_lower for kw in ["帮助", "功能", "其他"]):
                response_msg = """📋 我的功能：
1. 查询产品 - 了解各类套餐
2. 推荐产品 - 获取个性化推荐
3. 订购产品 - 办理新套餐
4. 查询订单 - 查看办理记录
5. 人工客服 - 转接人工服务

请直接输入您想了解的内容："""
                state.set_topic("menu")
            else:
                # 使用 LLM 生成回复（含上下文）
                # 将话题信息加入提示
                topic_hint = f"\n[提示: 用户正在讨论'{state.last_topic}'话题，如果和之前话题相关，请结合之前的对话内容]" if state.last_topic else ""
                
                llm_prompt = f"""{context_prompt}{topic_hint}

请用中文简洁回复，不超过80字。"""
                response_msg = self.llm_service.chat(llm_prompt)
                state.set_topic(detected_topic or state.last_topic or "chat")
            
            # 记录助手回复
            state.add_message("assistant", response_msg)
            
            return {"type": response_type, "message": response_msg}
            
        except Exception as e:
            print(f"Agent error: {e}")
            # 出错时回退
            return await self._fallback_handle(message, state)

    async def _fallback_handle(self, message: str, state: CRMState) -> Dict:
        """出错时的回退处理"""
        message_lower = message.lower()
        
        if "5g" in message_lower or "套餐" in message_lower or "产品" in message_lower:
            result = await self.api_client.get_products(keyword="5G" if "5g" in message_lower else None)
            if result.get("success"):
                products = result.get("products", [])
                msg = "为您找到以下产品：\n\n" + "\n".join([
                    f"📦 {p['name']} - {p['price']}元/月"
                    for p in products
                ])
                return {"type": "product_list", "message": msg}
        
        return {
            "type": "text",
            "message": "抱歉，服务暂时不可用。请尝试：\n• 输入'5G套餐'查询产品\n• 说'登录'完成身份验证"
        }