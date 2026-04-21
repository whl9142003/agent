"""
CRM Agent Business Logic
CRM营业受理智能体核心业务逻辑
"""
import json
import httpx
from typing import Optional, Dict, List, Any
from datetime import datetime


class CRMState:
    """会话状态管理"""

    def __init__(self):
        self.authenticated = False
        self.customer_id: Optional[str] = None
        self.customer_name: Optional[str] = None
        self.phone: Optional[str] = None
        self.account_balance: float = 0.0
        self.current_package: str = ""
        self.current_order: Optional[Dict] = None
        self.conversation_history: List[Dict] = []

    def to_dict(self) -> Dict:
        return {
            "authenticated": self.authenticated,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "phone": self.phone,
            "account_balance": self.account_balance,
            "current_package": self.current_package,
            "current_order": self.current_order,
            "conversation_history": self.conversation_history
        }

    def get_state_description(self) -> str:
        if not self.authenticated:
            return "未认证"
        return f"已认证 - {self.customer_name} - 套餐:{self.current_package}"


class CRMAPIClient:
    """CRM API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_verification_code(self, phone: str) -> Dict:
        """发送验证码"""
        response = await self.client.post(
            f"{self.base_url}/api/auth/send-code",
            json={"phone": phone}
        )
        return response.json()

    async def authenticate(self, phone: str, code: str = None,
                          password: str = None, auth_type: str = "password") -> Dict:
        """身份认证 - 使用密码登录"""
        auth_data = {
            "phone": phone,
            "auth_type": auth_type,
            "password": password
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/api/auth/login",
                json=auth_data
            )
            return response.json()
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def get_products(self, keyword: str = None, category: str = None) -> Dict:
        """获取产品列表"""
        params = {}
        if keyword:
            params["keyword"] = keyword
        if category:
            params["category"] = category

        response = await self.client.get(
            f"{self.base_url}/api/products",
            params=params
        )
        return response.json()

    async def get_product_detail(self, product_id: str) -> Dict:
        """获取产品详情"""
        response = await self.client.get(
            f"{self.base_url}/api/products/{product_id}"
        )
        return response.json()

    async def get_recommendations(self, customer_id: str) -> Dict:
        """获取产品推荐"""
        response = await self.client.get(
            f"{self.base_url}/api/products/recommend/{customer_id}"
        )
        return response.json()

    async def create_order(self, customer_id: str, product_id: str,
                          product_name: str, price: float) -> Dict:
        """创建订单"""
        response = await self.client.post(
            f"{self.base_url}/api/orders",
            json={
                "customer_id": customer_id,
                "product_id": product_id,
                "product_name": product_name,
                "price": price
            }
        )
        return response.json()

    async def get_orders(self, customer_id: str) -> Dict:
        """获取订单列表"""
        response = await self.client.get(
            f"{self.base_url}/api/orders/{customer_id}"
        )
        return response.json()

    async def get_order_detail(self, order_id: str) -> Dict:
        """获取订单详情"""
        response = await self.client.get(
            f"{self.base_url}/api/orders/detail/{order_id}"
        )
        return response.json()

    async def process_payment(self, order_id: str, customer_id: str,
                             payment_method: str = "account_balance") -> Dict:
        """处理支付"""
        response = await self.client.post(
            f"{self.base_url}/api/payment/pay",
            json={
                "order_id": order_id,
                "customer_id": customer_id,
                "payment_method": payment_method
            }
        )
        return response.json()

    async def get_customer_info(self, customer_id: str) -> Dict:
        """获取客户信息"""
        response = await self.client.get(
            f"{self.base_url}/api/customer/{customer_id}"
        )
        return response.json()


class CRMAgent:
    """CRM营业受理智能体"""

    def __init__(self, api_client: CRMAPIClient, llm_service):
        self.api_client = api_client
        self.llm_service = llm_service
        self.sessions: Dict[str, CRMState] = {}

    def get_session(self, session_id: str) -> CRMState:
        """获取或创建会话状态"""
        if session_id not in self.sessions:
            self.sessions[session_id] = CRMState()
        return self.sessions[session_id]

    def clear_session(self, session_id: str):
        """清除会话状态"""
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def process_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """处理用户消息"""
        state = self.get_session(session_id)

        # 添加用户消息到历史
        state.conversation_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # 意图识别和路由
        response = await self._route_message(session_id, message, state)

        # 添加助手消息到历史
        state.conversation_history.append({
            "role": "assistant",
            "content": response.get("message", ""),
            "timestamp": datetime.now().isoformat()
        })

        return response

    async def _route_message(self, session_id: str, message: str,
                            state: CRMState) -> Dict[str, Any]:
        """根据会话状态路由消息"""
        message_lower = message.lower()

        # 查询产品 - 不需要登录
        if any(kw in message_lower for kw in ["套餐", "产品", "流量", "5g", "4g", "多少钱", "价格"]):
            return await self._handle_product_query(session_id, message, state)

        # 推荐产品 - 不需要登录
        if any(kw in message_lower for kw in ["推荐", "适合", "帮我选"]):
            return await self._handle_product_recommend(session_id, message, state)

        # 检查是否需要身份认证（其他操作需要登录）
        if not state.authenticated:
            return await self._handle_authentication(session_id, message, state)

        # 已认证状态下的路由
        # 查询订单
        if any(kw in message_lower for kw in ["订单", "进度", "状态", "查询"]):
            return await self._handle_order_query(session_id, message, state)

        # 订购
        if any(kw in message_lower for kw in ["订购", "办理", "开通", "购买", "要这个"]):
            return await self._handle_order_create(session_id, message, state)

        # 支付
        if any(kw in message_lower for kw in ["支付", "付款", "确认"]):
            return await self._handle_payment(session_id, message, state)

        # 转人工
        if any(kw in message_lower for kw in ["转人工", "人工客服", "人工服务"]):
            return {
                "type": "transfer_to_agent",
                "message": "好的，正在为您转接人工客服，请稍候..."
            }

        # 默认：显示菜单
        return await self._show_menu(session_id, state)

    async def _handle_authentication(self, session_id: str,
                                     message: str, state: CRMState) -> Dict[str, Any]:
        """处理身份认证 - 用户主动要求登录"""

        # 检查是否是主动说"登录"
        message_lower = message.lower()
        if any(kw in message_lower for kw in ["登录", "登陆", "登录认证", "验证"]):
            return {
                "type": "auth_required",
                "message": "🔐 请输入您的手机号码和服务密码完成登录（格式：手机号 密码）\n\n例如：15300000574 Tianyuan@410"
            }

        # 检查是否是手机号+密码格式 "手机号 密码" 或 "手机号,密码"
        import re
        phone_pattern = r"1[3-9]\d{9}"
        phone_match = re.search(phone_pattern, message)

        if phone_match and (" " in message or "," in message):
            # 提取手机号和密码
            parts = re.split(r"[,\s]+", message)
            phone = phone_match.group()
            password = None
            for p in parts:
                if len(p) >= 6 and not p.isdigit():
                    password = p
                    break

            if not password:
                # 没有单独密码，提示输入密码
                state.phone = phone
                return {
                    "type": "auth_password",
                    "message": f"请输入服务密码完成登���",
                    "phone": phone
                }

            # 直接调用CRM登录接口
            result = await self.api_client.authenticate(phone, password=password)
            if result.get("success"):
                customer = result.get("customer", {})
                state.authenticated = True
                state.customer_id = customer.get("customer_id")
                state.customer_name = customer.get("name")
                state.phone = customer.get("phone")
                state.account_balance = customer.get("account_balance", 0)
                state.current_package = customer.get("current_package", "")

                return {
                    "type": "auth_success",
                    "message": f"✅ 认证成功！\n\n尊敬的用户，您好！\n您当前使用的是：{state.current_package}\n账户余额：{state.account_balance}元\n\n请问有什么可以帮您？\n• 查询产品信息\n• 办理业务\n• 查询订单",
                    "customer": customer
                }
            else:
                return {
                    "type": "auth_failed",
                    "message": "登录失败，请检查手机号和密码后重试。"
                }

        # 检查是否需要密码登录
        if state.phone and not state.authenticated:
            # 尝试直接用message作为密码登录
            result = await self.api_client.authenticate(state.phone, password=message)
            if result.get("success"):
                customer = result.get("customer", {})
                state.authenticated = True
                state.customer_id = customer.get("customer_id")
                state.customer_name = customer.get("name")
                state.phone = customer.get("phone")
                state.account_balance = customer.get("account_balance", 0)
                state.current_package = customer.get("current_package", "")

                return {
                    "type": "auth_success",
                    "message": f"✅ 认证成功！\n\n尊敬的用户，您好！\n您当前使用的是：{state.current_package}\n账户余额：{state.account_balance}元\n\n请问有什么可以帮您？",
                    "customer": customer
                }
            else:
                return {
                    "type": "auth_failed",
                    "message": "密码错误，请重新输入。"
                }

        # 初始认证请求 - 返回欢迎菜单，可选择登录
        return {
            "type": "welcome",
            "message": "🤖 欢迎使用营业受理机器人！\n\n我可以为您提供以下服务：\n\n📦 产品查询 - 了解各类套餐\n📋 订单查询 - 查看办理记录\n💬 人工客服 - 转接人工服务\n\n您可以直接输入您想了解的内容。\n\n💡 提示：订购产品或查询订单需要先登录\n\n请先输入您想了解的产品（如：5G套餐）或直接说'登录'完成身份验证"
        }

        # 检查是否输入密码
        if state.phone and not state.authenticated:
            result = await self.api_client.authenticate(
                state.phone, password=message, auth_type="password"
            )
            if result.get("success"):
                customer = result.get("customer", {})
                state.authenticated = True
                state.customer_id = customer.get("customer_id")
                state.customer_name = customer.get("name")
                state.phone = customer.get("phone")
                state.account_balance = customer.get("account_balance", 0)
                state.current_package = customer.get("current_package", "")

                return {
                    "type": "auth_success",
                    "message": f"✅ 认证成功！\n\n尊敬的用户，您好！\n您当前使用的是：{state.current_package}\n账户余额：{state.account_balance}元\n\n请问有什么可以帮您？",
                    "customer": customer
                }

        # 初始认证请求
        return {
            "type": "auth_required",
            "message": "🤖 欢迎使用CRM营业受理服务！\n\n为了提供个性化服务，请先完成身份验证。\n\n请输入您的手机号码："
        }

    async def _handle_product_query(self, session_id: str,
                                     message: str, state: CRMState) -> Dict[str, Any]:
        """处理产品查询 - 不需要登录"""
        # 提取关键词
        keyword = None
        if "5g" in message.lower():
            keyword = "5G"
        elif "4g" in message.lower():
            keyword = "4G"
        elif "流量" in message:
            keyword = "流量"

        result = await self.api_client.get_products(keyword=keyword)

        if result.get("success"):
            products = result.get("products", [])
            if not products:
                return {
                    "type": "product_not_found",
                    "message": "抱歉，未找到相关产品。请尝试其他关键词。"
                }

            # 构建产品列表消息
            product_list = "\n".join([
                f"\n📦 {p['name']}\n   价格：{p['price']}元/月\n   包含：{p['data_quota']}流量 + {p['voice_quota']}通话\n   适合：{p['description']}\n   [回复'订购' + 产品名称可立即订购]"
                for p in products
            ])

            return {
                "type": "product_list",
                "message": f"为您找到以下产品：{product_list}",
                "products": products
            }

        return {
            "type": "error",
            "message": "产品查询服务暂时不可用，请稍后重试。"
        }

    async def _handle_product_recommend(self, session_id: str,
                                        message: str, state: CRMState) -> Dict[str, Any]:
        """处理产品推荐 - 不需要登录"""
        result = await self.api_client.get_recommendations(state.customer_id)

        if result.get("success"):
            recommendations = result.get("recommendations", [])
            usage = result.get("customer_usage", {})

            msg = f"📊 根据您的使用情况，为您推荐：\n"
            if usage:
                msg += f"\n您的月均使用情况：\n"
                msg += f"• 流量：{usage.get('avg_data', 'N/A')}\n"
                msg += f"• 通话：{usage.get('avg_voice', 'N/A')}\n"

            product_list = "\n".join([
                f"\n📦 {p['name']}\n   价格：{p['price']}元/月\n   包含：{p['data_quota']} + {p['voice_quota']}\n   适合：{p['description']}\n   [回复'订购'可立即办理]"
                for p in recommendations
            ])

            return {
                "type": "product_recommend",
                "message": msg + product_list,
                "recommendations": recommendations
            }

        return {
            "type": "error",
            "message": "推荐服务暂时不可用，请稍后重试。"
        }

    async def _handle_order_query(self, session_id: str,
                                 message: str, state: CRMState) -> Dict[str, Any]:
        """处理订单查询"""
        # 检查登录状态
        if not state.authenticated:
            return {
                "type": "auth_required",
                "message": "🔐 查询订单需要先登录\n\n请输入您的手机号码和服务密码完成登录（格式：手机号 密码）\n\n例如：15300000574 Tianyuan@410"
            }

        result = await self.api_client.get_orders(state.customer_id)

        if result.get("success"):
            orders = result.get("orders", [])
            if not orders:
                return {
                    "type": "order_empty",
                    "message": "您暂无订单记录。\n\n是否需要了解我们的产品？"
                }

            # 简化订单列表显示
            order_list = "\n".join([
                f"\n📋 {o['product_name']}\n   订单编号：{o['order_id']}\n   状态：{self._get_status_text(o['status'])}\n   创建时间：{o['create_time'][:19] if o.get('create_time') else 'N/A'}\n   [回复'详情 {订单后4位}'查看详情]"
                for o in orders
            ])

            return {
                "type": "order_list",
                "message": f"您的订单列表：{order_list}",
                "orders": orders
            }

        return {
            "type": "error",
            "message": "订单查询服务暂时不可用，请稍后重试。"
        }

    async def _handle_order_create(self, session_id: str,
                                   message: str, state: CRMState) -> Dict[str, Any]:
        """处理订单创建"""
        # 检查登录状态
        if not state.authenticated:
            return {
                "type": "auth_required",
                "message": "🔐 订购产品需要先登录\n\n请输入您的手机号码和服务密码完成登录（格式：手机号 密码）\n\n例如：15300000574 Tianyuan@410"
            }

        # 从历史消息中获取选择的产品
        products = []
        for msg in reversed(state.conversation_history):
            if msg.get("role") == "assistant" and msg.get("type") in ["product_list", "product_recommend"]:
                products = msg.get("products", msg.get("recommendations", []))
                break

        if not products:
            # 需要先查询产品
            return {
                "type": "need_product",
                "message": "请先选择您要订购的产品。\n\n您可以：\n• 回复'推荐'获取个性化推荐\n• 回复'5G套餐'查看5G产品"
            }

        # 使用第一个产品创建订单
        product = products[0]
        result = await self.api_client.create_order(
            customer_id=state.customer_id,
            product_id=product["product_id"],
            product_name=product["name"],
            price=product["price"]
        )

        if result.get("success"):
            order = result.get("order")
            state.current_order = order

            return {
                "type": "order_created",
                "message": f"📋 订单已创建！\n\n订单编号：{order['order_id']}\n产品名称：{order['product_name']}\n支付金额：{order['price']}元\n\n您的账户余额：{state.account_balance}元\n\n请回复'确认支付'完成付款",
                "order": order
            }

        return {
            "type": "error",
            "message": "订单创建失败，请稍后重试或转人工服务。"
        }

    async def _handle_payment(self, session_id: str,
                             message: str, state: CRMState) -> Dict[str, Any]:
        """处理支付"""
        # 检查登录状态
        if not state.authenticated:
            return {
                "type": "auth_required",
                "message": "🔐 支付需要先登录\n\n请输入您的手机号码和服务密码完成登录（格式：手机号 密码）\n\n例如：15300000574 Tianyuan@410"
            }

        if not state.current_order:
            return {
                "type": "no_order",
                "message": "您当前没有待支付的订单。"
            }

        result = await self.api_client.process_payment(
            order_id=state.current_order["order_id"],
            customer_id=state.customer_id
        )

        if result.get("success"):
            order = result.get("order")
            payment = result.get("payment", {})

            # 更新本地状态
            state.account_balance = payment.get("remaining_balance", state.account_balance)
            state.current_order = None

            return {
                "type": "payment_success",
                "message": f"✅ 支付成功！\n\n订单编号：{order['order_id']}\n支付金额：{payment.get('amount')}元\n支付方式：已有账户支付\n支付时间：{payment.get('payment_time', '')[:19]}\n\n🎉 恭喜您，业务办理成功！\n\n您可以：\n• 回复'查询订单'查看订单详情\n• 回复'继续'浏览更多产品",
                "order": order
            }
        else:
            return {
                "type": "payment_failed",
                "message": f"支付失败：{result.get('message', '未知错误')}\n\n请确认账户余额充足，或选择其他支付方式。"
            }

    async def _show_menu(self, session_id: str, state: CRMState) -> Dict[str, Any]:
        """显示菜单"""
        return {
            "type": "menu",
            "message": f"您好，{state.customer_name}！\n\n请问有什么可以帮您？\n\n1️⃣ 查询产品 - 了解各类套餐\n2️⃣ 产品推荐 - 获取个性化推荐\n3️⃣ 我的订单 - 查看订单列表\n4️⃣ 人工客服 - 转接人工服务\n\n请输入选项编号或直接描述您的需求："
        }

    def _mask_phone(self, phone: str) -> str:
        """脱敏手机号"""
        return phone[:3] + "****" + phone[-4:]

    def _get_status_text(self, status: str) -> str:
        """获取状态描述"""
        status_map = {
            "pending_payment": "待支付",
            "paid": "已支付",
            "processing": "处理中",
            "completed": "已完成",
            "cancelled": "已取消"
        }
        return status_map.get(status, status)
