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

import config
from services.knowledge_base import get_knowledge_base, KnowledgeBase
from services.i18n import t, format_message, format_offers_for_language, get_translations
from services.knowledge_map import get_product_offer_type_name, get_auto_renew_name, get_status_name, get_brand_name


# ============ CRM API Client ============

class CRMAPIClient:
    """CRM API 客户端 - 对接真实CRM业务系统"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.CRM_API_BASE_URL
        self._session = requests.Session()
        self._session.verify = False

    def _request(self, method: str, path: str, data: dict = None, params: dict = None) -> Dict:
        """统一请求方法"""
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                response = self._session.get(url, params=params, timeout=30)
            else:
                response = self._session.post(url, json=data, timeout=30)
            return response.json()
        except Exception as e:
            print(f"CRM API Error: {path} - {e}")
            return {"code": "1", "message": str(e)}

    def query_customer(self, phone: str) -> Dict:
        """客户查询接口 /CCInter/open/cust/query"""
        data = {"custVal": phone}
        return self._request("POST", "/CCInter/open/cust/query", data=data)

    def query_customer_offers(self, cust_id: str) -> Dict:
        """客户订购产品查询接口 /CCInter/open/cust/offers"""
        data = {"custId": cust_id}
        return self._request("POST", "/CCInter/open/cust/offers", data=data)

    def query_sub_offers(self, offer_inst_id: str) -> Dict:
        """附属销售品查询接口 /CCInter/open/cust/sub/offers"""
        data = {"offerInstId": offer_inst_id}
        return self._request("POST", "/CCInter/open/cust/sub/offers", data=data)

    async def send_verification_code(self, phone: str) -> Dict:
        resp = self._session.post(f"{self.base_url}/api/auth/send-code", json={"phone": phone}, timeout=30)
        return resp.json()

    def authenticate(self, phone: str, code: str = None, password: str = None, auth_type: str = "password") -> Dict:
        auth_data = {"phone": phone, "auth_type": auth_type or "password", "password": password}
        try:
            resp = self._session.post(f"{self.base_url}/api/auth/login", json=auth_data, timeout=30)
            result = resp.json()
            print(f"[APIClient] Login response: {result}")
            return result
        except Exception as e:
            print(f"[APIClient] Login error: {e}")
            return {"success": False, "message": str(e)}

    async def get_products(self, keyword: str = None, category: str = None) -> Dict:
        params = {}
        if keyword: params["keyword"] = keyword
        if category: params["category"] = category
        resp = self._session.get(f"{self.base_url}/api/products", params=params, timeout=30)
        return resp.json()

    async def get_recommendations(self, customer_id: str) -> Dict:
        resp = self._session.get(f"{self.base_url}/api/products/recommend/{customer_id}", timeout=30)
        return resp.json()

    async def create_order(self, customer_id: str, product_id: str, product_name: str, price: float) -> Dict:
        resp = self._session.post(f"{self.base_url}/api/orders", json={
            "customer_id": customer_id, "product_id": product_id,
            "product_name": product_name, "price": price
        }, timeout=30)
        return resp.json()

    async def get_order_offers(self, customer_id: str) -> Dict:
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/order/offers",
            json={"custId": customer_id},
            timeout=30
        )
        return resp.json()

    async def query_offers(self, keyword: str = "") -> Dict:
        """查询可订购销售品"""
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/offers/query",
            json={"prodOfferNameOrBrandName": keyword},
            timeout=30
        )
        return resp.json()

    async def query_optgroup_offers(self, prod_offer_id: str) -> Dict:
        """获取附属销售品组"""
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/order/optgroup/offers",
            json={"pkgOfferId": prod_offer_id},
            timeout=30
        )
        return resp.json()

    async def get_orders(self, customer_id: str) -> Dict:
        resp = self._session.get(f"{self.base_url}/api/orders/{customer_id}", timeout=30)
        return resp.json()

    async def process_payment(self, order_id: str, customer_id: str, payment_method: str = "account_balance") -> Dict:
        resp = self._session.post(f"{self.base_url}/api/payment/pay", json={
            "order_id": order_id, "customer_id": customer_id, "payment_method": payment_method
        }, timeout=30)
        return resp.json()


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
        self.last_topic: Optional[str] = None
        self.offers: List[Dict] = []

        # ========== 记忆 & 上下文管理 ==========
        # 短期记忆：本轮办理流程
        self.flow_context = {
            "step": None,           # 当前流程步骤: recommend/recommend_choose/confirm/ordering
            "target_offer": None,    # 用户选中的套餐
            "pending_question": None, # 待确认的问题
            "last_offer_list": [],   # 上次推荐的套餐列表
            "clarification_needed": None,  # 待澄清的问题
        }

        # 长期记忆：用户画像
        self.user_profile = {
            "phone": None,           # 手机号
            "package": "",            # 当前套餐
            "tenure": 0,              # 在网时长(月)
            "consumption_level": "",  # 消费等级: 高/中/低
            "usage_pattern": "",      # 使用习惯: 大流量/普通/保号
            "preferences": [],       # 历史偏好: ["宽带", "流量多"]
            "last_interaction": None,  # 上次交互时间
        }

        # 会话超时管理
        self.last_message_time = None
        self.session_timeout_seconds = config.SESSION_CONFIG.get("session_timeout_seconds", 1800)  # 默认30分钟

        # 会话配置
        self.max_history = config.SESSION_CONFIG.get("max_history", 20)
        self.context_window = config.SESSION_CONFIG.get("context_window", 10)

    def update_user_profile(self, **kwargs):
        """更新用户画像"""
        for key, value in kwargs.items():
            if key in self.user_profile:
                self.user_profile[key] = value
        self.user_profile["last_interaction"] = datetime.now().isoformat()

    def set_flow_step(self, step: str, **context):
        """设置流程步骤和上下文"""
        self.flow_context["step"] = step
        for key, value in context.items():
            self.flow_context[key] = value
        self.last_message_time = datetime.now()

    def get_flow_step(self) -> str:
        """获取当前流程步骤"""
        return self.flow_context.get("step")

    def clear_flow(self):
        """清除短期流程记忆"""
        self.flow_context = {
            "step": None,
            "target_offer": None,
            "pending_question": None,
            "last_offer_list": [],
            "clarification_needed": None,
        }

    def check_session_timeout(self) -> bool:
        """检查会话是否超时"""
        from datetime import datetime as dt
        if self.last_message_time is None:
            self.last_message_time = dt.now()
            return False

        now = dt.now()
        elapsed = (now - self.last_message_time).total_seconds()

        if elapsed > self.session_timeout_seconds:
            print(f"[State] Session timeout after {elapsed:.0f}s, resetting flow context")
            self.clear_flow()
            return True

        return False

    def set_offers(self, offers: List[Dict]):
        """设置客户订购产品列表"""
        self.offers = offers

    def set_offers(self, offers: List[Dict]):
        """设置客户订购产品列表"""
        self.offers = offers

    def get_offers_summary(self) -> str:
        """获取订购产品摘要"""
        if not self.offers:
            return "暂无订购产品"
        lines = []
        for offer in self.offers[:5]:
            lines.append(f"📦 {offer.get('offerName', 'N/A')} ({offer.get('regionName', 'N/A')})")
        return "\n".join(lines)

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

    def get_conversation_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history

    def set_conversation_history(self, history: List[Dict]):
        """设置对话历史"""
        self.conversation_history = history or []

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
            "last_topic": self.last_topic,
            "offers": self.offers
        }
    
    def from_dict(self, data: Dict):
        """从字典恢复状态"""
        self.authenticated = data.get("authenticated", False)
        self.customer_id = data.get("customer_id")
        self.customer_name = data.get("customer_name")
        self.phone = data.get("phone")
        self.account_balance = data.get("account_balance", 0.0)
        self.current_package = data.get("current_package", "")
        self.current_order = data.get("current_order")
        self.conversation_history = data.get("conversation_history", [])
        self.last_topic = data.get("last_topic")
        self.offers = data.get("offers", [])


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
        self.system_prompt = """你是电信CRM营业受理系统的智能客服助手，专门帮助用户办理电信业务。

你的职责范围：
1. 产品查询：查询5G套餐、4G套餐、流量包等电信产品信息
2. 账户服务：登录认证、账户信息查询、套餐变更
3. 业务办理：订购套餐、办理增值业务、取消业务
4. 订单查询：查询办理进度、订单状态
5. 问题解答：解答电信业务相关问题

禁止事项：
1. 不要回答与电信业务无关的问题（如：大模型、技术实现、其他公司等）
2. 不要透露使用的技术实现（如：大模型、API等）
3. 不要进行与电信业务无关的闲聊
4. 用户询问无关话题时，引导回业务主题

业务规则：
1. 产品查询和推荐不需要登录，任何用户都可以使用
2. 订购产品、查询订单、支付需要用户先登录
3. 用户说要"登录"时，引导用户输入：手机号码 空格 密码（如：13800138000 123456）
4. 用户选择订购时，检查是否已登录，未登录提示先登录
5. 注意：目前只支持密码登录，暂不支持短信验证码
6. 每个会话只能看到当前客户的对话，不能看到其他客户的对话
7. 已登录客户只能查询自己名下的号码，不能查询其他人的号码
8. 查询号码时必须验证号码归属，跨客户查询属于越权操作
9. 未登录状态下查询号码，必须先引导用户登录认证

回答要求：
1. 使用中文回复
2. 保持友好、专业
3. 如实传达工具返回的结果
4. 根据用户已登录状态提供个性化服务
5. 如果用户询问无关话题，引导回电信业务主题
6. 回复简洁明了，不超过200字
7. 遇到无法处理的问题，提示用户联系人工客服或换个方式描述
8. 号码归属验证失败时，提示"您没有权限查询该号码信息"

登录引导示例：
当用户要求登录时，请使用以下格式引导：
"好的，为您提供登录服务。\n\n请输入手机号码和密码进行登录，格式：手机号码 空格 密码（如：13800138000 123456）。登录后即可办理业务、查询套餐或订单。"

未登录提示示例：
当用户需要登录才能操作时（如查询订单），请使用以下格式：
"您好！查询订单需要验证您的身份信息。为了保障您的账户安全，请先登录。\n\n登录格式：手机号码 空格 密码（如：13800138000 123456）"

无权限提示示例：
当客户查询非本人号码时，请使用以下格式：
"您好！您没有权限查询该号码信息。如需帮助，请联系客服或前往营业厅。"

用户登录后，你可以查询和展示��
- 当前使用的套餐
- 账户余额
- 已订购的产品列表（含主销售品和附属销售品）
- 订单列表
"""

    def get_session(self, session_id: str) -> CRMState:
        if session_id not in self.sessions:
            self.sessions[session_id] = CRMState()
        return self.sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def _format_offers_v2(self, offers: List[Dict], language: str = "zh") -> str:
        """格式化订购销售品信息_v2 - 按照规范格式输出"""
        trans = get_translations(language)
        if not offers:
            return trans["no_offers"]

        lines = []
        lines.append(f"🔹 {trans['product_inquiry']}")

        for idx, offer in enumerate(offers, 1):
            offer_name = offer.get("offerName", trans["no_data"])
            eff_date = offer.get("effDate", "")
            exp_date = offer.get("expDate", "")
            subscribe_date = offer.get("subscribeDate", "")
            product_type = offer.get("productOfferType", "")

            eff_str = eff_date[:10] if eff_date and len(eff_date) >= 10 else ""
            exp_str = exp_date[:10] if exp_date and len(exp_date) >= 10 else ""

            lines.append("")
            lines.append(f"🔸 主套餐{idx}：**{offer_name}**")
            lines.append(f"　　📅 {trans['effective_time']}：{eff_str or trans['no_data']}")
            lines.append(f"　　📅 {trans['expiration_time']}：{exp_str or trans['no_data']}")
            if subscribe_date:
                sub_str = subscribe_date[:10] if len(subscribe_date) >= 10 else subscribe_date
                lines.append(f"　　📆 {trans['order_date']}：{sub_str}")

            type_name = get_product_offer_type_name(product_type)
            lines.append(f"　　📋 {trans['status']}：{type_name}")

            sub_offers = offer.get("subOfferInst", [])

            if sub_offers:
                lines.append("")
                lines.append(f"▫️ {trans['product_name']}的子销售品：")
                for sub in sub_offers:
                    sub_name = sub.get("offerName", trans["no_data"])
                    billing_no = sub.get("billingNo", "")
                    contract_cd = sub.get("contractCd", "")
                    sub_eff = sub.get("effDate", "")
                    sub_exp = sub.get("expDate", "")

                    sub_eff_str = sub_eff[:10] if sub_eff and len(sub_eff) >= 10 else ""
                    sub_exp_str = sub_exp[:10] if sub_exp and len(sub_exp) >= 10 else ""

                    lines.append("")
                    lines.append(f"　　📱 **{sub_name}**")
                    if billing_no:
                        lines.append(f"　　　　📞 **号码**：{billing_no}")
                    if contract_cd:
                        lines.append(f"　　　　📜 **合约编号**：{contract_cd}")
                    lines.append(f"　　　　📅 {trans['effective_time']}：{sub_eff_str or trans['no_data']}")
                    lines.append(f"　　　　📅 {trans['expiration_time']}：{sub_exp_str or trans['no_data']}")
            else:
                lines.append("")
                lines.append(f"　　（无子销售品）")

        return "\n".join(lines).strip()

    def _format_available_offers(self, offers: List[Dict], language: str = "zh") -> str:
        """格式化可订购销售品信息 - 包含主销售品和附属销售品组"""
        trans = get_translations(language)
        if not offers:
            return trans["no_offers"]

        from services.knowledge_map import get_brand_name, get_auto_renew_name

        lines = []
        lines.append(f"🔹 {trans['product_inquiry']}")

        for idx, offer in enumerate(offers, 1):
            name = offer.get("prodOfferName", trans["no_data"])
            desc = offer.get("offerDescription", "")
            fee_desc = offer.get("offerFeeDescription", "")
            brand_id = offer.get("brandId", "")
            eff_date = offer.get("effDate", "")
            exp_date = offer.get("expDate", "")
            auto_renew = offer.get("automaticRenewal", "")

            brand_name = get_brand_name(brand_id) if brand_id else ""
            auto_renew_name = get_auto_renew_name(auto_renew) if auto_renew else ""

            eff_str = eff_date[:10] if eff_date and len(eff_date) >= 10 else ""
            exp_str = exp_date[:10] if exp_date and len(exp_date) >= 10 else ""

            lines.append("")
            lines.append(f"🔸 {trans['product_inquiry']}{idx}：**{name}**")
            if desc:
                lines.append(f"　　📝 描述：{desc}")
            if fee_desc:
                lines.append(f"　　💰 资费：{fee_desc}")
            if brand_name and brand_name != brand_id:
                lines.append(f"　　🏷️ 品牌：{brand_name}")
            if eff_str and eff_str != exp_str:
                lines.append(f"　　📅 生效：{eff_str}")
                lines.append(f"　　📅 失效：{exp_str}")
            if auto_renew_name and auto_renew_name != auto_renew:
                lines.append(f"　　🔄 自动续费：{auto_renew_name}")

            opt_groups = offer.get("optGroups", [])
            if opt_groups:
                for group in opt_groups:
                    group_name = group.get("optGroupName", "")
                    opt_list = group.get("optOfferList", [])

                    if group_name and opt_list:
                        lines.append("")
                        lines.append(f"▫️ {group_name}（可选）：")
                        for opt in opt_list:
                            opt_name = opt.get("prodOfferName", trans["no_data"])
                            opt_desc = opt.get("offerDescription", "")
                            opt_auto = get_auto_renew_name(opt.get("automaticRenewal", ""))

                            lines.append(f"　　　📱 **{opt_name}**")
                            if opt_desc and opt_desc != opt_name:
                                lines.append(f"　　　　　📝 {opt_desc}")
                            if opt_auto and opt_auto != opt_auto:
                                lines.append(f"　　　　　🔄 {opt_auto}")
            else:
                lines.append(f"　　（无可选附属销售品）")

        return "\n".join(lines).strip()

    def _format_order_offers(self, offers: List[Dict], language: str = "zh") -> str:
        """格式化可订购销售品信息"""
        trans = get_translations(language)
        if not offers:
            return trans["no_offers"]
        
        lines = []
        for offer in offers:
            name = offer.get("prodOfferName", "未知")
            desc = offer.get("offerDescription", "")
            fee_desc = offer.get("offerFeeDescription", "")
            brand_id = offer.get("brandId", "")
            eff_date = offer.get("effDate", "")
            exp_date = offer.get("expDate", "")
            
            eff_str = eff_date[:10] if eff_date and len(eff_date) >= 10 else ""
            exp_str = exp_date[:10] if exp_date and len(exp_date) >= 10 else ""
            
            brand_name = ""
            if brand_id:
                brand_map = {"1": "品牌A", "2": "品牌B", "3": "品牌C", "1,2": "品牌A/B"}
                brand_name = brand_map.get(brand_id, f"品牌{brand_id}")
            
            lines.append(f"📋 {name}")
            if desc:
                lines.append(f"   描述：{desc}")
            if fee_desc:
                lines.append(f"   资费：{fee_desc}")
            if brand_name:
                lines.append(f"   品牌：{brand_name}")
            lines.append(f"   生效时间：{eff_str or '暂无'}")
            lines.append(f"   失效时间：{exp_str or '暂无'}")
            lines.append("")
        
        return "\n".join(lines).strip()

    async def process_message(self, session_id: str, message: str, language: str = "zh") -> Dict[str, Any]:
        """处理用户消息 - 使用 LangChain LLM，支持上下文记忆和国际化"""
        state = self.get_session(session_id)

        # 检查会话超时，自动重置短期流程记忆
        if state.check_session_timeout():
            print(f"[Agent] Session {session_id} timeout, cleared flow context")

        print(f"[Agent] Session {session_id} state: authenticated={state.authenticated}, customer_id={state.customer_id}")
        print(f"[Agent] Flow step: {state.get_flow_step()}, User profile: {state.user_profile.get('phone')}")
        trans = get_translations(language)
        
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
            phone = phone_match.group()
            parts = re.split(r"[,\s]+", message)
            # 密码可以是纯数字(6位以上)或字母数字组合
            password = next((p for p in parts if len(p) >= 6 and p != phone), None)

            if password:
                # 调用登录接口（mock-api中已包含Step 2/3/4的调用）
                auth_result = self.api_client.authenticate(phone, password=password)
                print(f"[Agent] Auth result: {auth_result}")
                
                if not auth_result.get("success"):
                    error_msg = auth_result.get("message", trans["login_failed"])
                    return {"type": "auth_failed", "message": f"{trans['login_failed']}：{error_msg}"}
                
                # 从登录结果中获取客户信息和已订购产品
                customer = auth_result.get("customer", {})
                cust_id = customer.get("customer_id", "")
                cust_name = customer.get("name", "") or customer.get("full_name", "")
                offers_list = customer.get("offers", [])
                print(f"[Agent] Offers list: {offers_list}")
                
                # 查询三户信息
                cust_result = self.api_client.query_customer(phone)
                cust_info = {}
                if cust_result.get("code") == "0" and cust_result.get("resultObj", {}).get("list"):
                    cust_data = cust_result["resultObj"]["list"][0]
                    cust_info = {
                        "custId": cust_data.get("custId", ""),
                        "custName": cust_data.get("custName", ""),
                        "acctId": cust_data.get("acctId", ""),
                        "subscriberId": cust_data.get("subscriberId", "")
                    }
                
                # 设置会话状态
                state.authenticated = True
                state.customer_id = cust_id
                state.customer_name = cust_name
                state.phone = phone
                state.set_offers(offers_list)

                # 更新用户画像
                current_pkg = customer.get("current_package", "")
                acct_balance = customer.get("account_balance", 0)
                state.update_user_profile(
                    phone=phone,
                    package=current_pkg,
                    consumption_level="中" if acct_balance > 100 else "低"
                )

                # 格式化销售品信息
                offers_msg = format_offers_for_language(offers_list, language)

                success_msg = f"✅ 登录成功！欢迎回来~ 我是营业厅客服小信，帮您查到了您名下的套餐信息：\n\n{offers_msg if offers_msg else trans['no_offers']}\n\n{trans['dear_user']}，请问还有什么可以帮到您的？"

                state.set_topic("login")
                state.add_message("assistant", success_msg)

                return {
                    "type": "auth_success",
                    "message": success_msg,
                    "customer": {
                        "customer_id": cust_id, 
                        "name": cust_name, 
                        "phone": phone,
                        "account_balance": customer.get("account_balance", 0),
                        "current_package": customer.get("current_package", "")
                    }
}
        
        # 使用 LLM 判断用户意图并生成回复（含上下文记忆）
        try:
            # 构建上下文信息
            user_info = state.get_user_info()
            conversation_context = state.get_conversation_context()
            
            # 构建意图判断提示
            intent_prompt = f"""你是电信营业厅智能客服小信，需要快速判断用户想做什么。

用户说：{message}
登录状态：{'已登录' if state.authenticated else '未登录'}
对话历史：{conversation_context[-200:] if conversation_context else '无'}

请快速判断（只回一个词）：
- 推荐套餐：用户问"有什么套餐推荐"、"想换个套餐"、"哪个划算"、"我流量不够用"、"想便宜点"、"家里要宽带"这类
- 办理业务：用户说"要办理"、"帮我开卡"、"加个流量包"、"降套餐"
- 查询订单：用户说"查一下我办的订单"、"订单到哪了"、"我的订单"
- 咨询问题：用户问规则、问费用、问怎么操作等
- 闲聊/其他：问候、闲聊、不会等

自然口语理解：
- "我流量不够用" → 推荐套餐（需要流量）
- "想便宜点" → 推荐套餐（需要性价比）
- "家里要宽带" → 推荐套餐（需要宽带）
- "能不能降套餐" → 办理业务（降套餐）
- "宽带怎么办" → 推荐套餐（需要宽带）

结合上下文判断更准：
- 用户之前说过流量不够，这次问流量包 → 推荐套餐
- 用户之前说过想便宜，这次问便宜的 → 推荐套餐
- 用户说"查查"之前办了什么 → 查询订单
- 用户问这个月流量怎么算 → 咨询问题

只返回一个词（推荐套餐/办理业务/查询订单/咨询问题/其他）："""
            
            # 调用LLM判断意图
            print(f"[Agent] Calling LLM for intent check...")
            intent_decision = self.llm_service.invoke(intent_prompt)
            intent_text = intent_decision.content.strip().lower() if hasattr(intent_decision, 'content') else str(intent_decision).lower()
            
            print(f"[Agent] Intent check for '{message}': '{intent_text}'")
            print(f"[Agent] Authenticated: {state.authenticated}, CustomerID: {state.customer_id}")
            
# 查询订单
            if "查询订单" in intent_text:
                if state.authenticated and state.customer_id:
                    print(f"[Agent] Querying orders for customer: {state.customer_id}")
                    orders = await self.api_client.get_orders(state.customer_id)
                    print(f"[Agent] Orders result: {orders}")
                    if orders.get("success"):
                        order_list = orders.get("orders", [])
                        if order_list:
                            order_msg = f"📋 帮您查到了这些订单：\n\n"
                            for order in order_list:
                                product = order.get('product_name', trans['no_data'])
                                status = order.get('status', trans['no_data'])
                                create_time = order.get('create_time', trans['no_data'])
                                order_no = order.get('order_id', '')[-6:] if order.get('order_id') else ''

                                # 友好风格的状态转换
                                status_text = "已完成" if status == "已完成" else "处理中"

                                order_msg += f"📦 {product}\n"
                                order_msg += f"   状态：{status_text}\n"
                                order_msg += f"   订单号尾号：{order_no}\n"
                                order_msg += f"   时间：{create_time[:16] if create_time else ''}\n\n"

                            order_msg += "请问还有其他需要帮您查的吗？"
                            return {"type": "order_list", "message": order_msg}
                        else:
                            return {"type": "text", "message": f"您目前还没有办理中的订单哦~ 需要帮您推荐什么套餐吗？"}
                    else:
                        return {"type": "text", "message": f"抱歉，帮您查订单的时候遇到点问题，请您稍后再试~"}
                else:
                    return {"type": "auth_required", "message": f"亲，查询订单需要先登录验证一下哦~ 输入手机号和密码登录（手机号 空格 密码）就可以啦"}

            # 推荐套餐 - 查询可订购销售品
            if "推荐套餐" in intent_text:
                # 首先调用 /CCInter/open/offers/query 获取主销售品
                keyword = ""
                print(f"[Agent] Querying available offers with keyword: {keyword}")
                offers_result = await self.api_client.query_offers(keyword)
                print(f"[Agent] Offers result: {offers_result}")

                if offers_result.get("code") == "0":
                    offer_list = offers_result.get("resultObj", [])

                    # 对每个主销售品，获取其附属销售品组
                    all_offers = []
                    for offer in offer_list:
                        prod_offer_id = str(offer.get("prodOfferId", ""))

                        # 调用 /CCInter/open/order/optgroup/offers 获取附属销售品
                        optgroup_result = await self.api_client.query_optgroup_offers(prod_offer_id)
                        opt_groups = optgroup_result.get("resultObj", [])

                        offer["optGroups"] = opt_groups
                        all_offers.append(offer)

                    formatted_offers = self._format_available_offers(all_offers, language)
                    return {
                        "type": "available_offers",
                        "message": formatted_offers + "\n\n请问您想了解哪一款？或者告诉我您的使用习惯（月租预算、流量需求、要不要宽带），我帮您推荐~",
                        "offers": all_offers
                    }
                else:
                    return {
                        "type": "text",
                        "message": f"❌ {trans['no_offers']}。"
                    }
            
# 构建完整的上下文提示，使用LLM生成回复
            context_prompt = f"""你是电信CRM营业受理智能客服助手，为用户提供电信业务咨询和办理服务。

【当前会话上下文】
{conversation_context}

【用户信息】
{user_info}

【用户最新消息】
{message}

【安全规则 - 重要！】
1. 每个客户的会话独立，不能查看其他客户的对话
2. 已登录客户只能查询自己名下的号码，不能查询其他人号码
3. 查询号码前必须验证号码归属：检查号码是否属于当前登录客户的手机号列表
4. 如果查询的号码不在客户本人名下，必须拒绝并提示："您好！您没有权限查询该号码信息。如需帮助，请联系客服或前往营业厅。"
5. 未登录状态下查询号码，引导用户登录："您好！查询号码需要先登录验证。请输入手机号码和密码进行登录，格式：手机号码 空格 密码（如：13800138000 123456）"

请根据上下文历史和当前话题，用中文回复用户，保持对话连贯性。如果用户切回之前的话题，需要结合之前的对话内容回复。

回复要求：
1. 简洁、专业、友好
2. 优先解答用户的电信业务问题
3. 如果用户询问功能可以说：可以帮您查询套餐、办理业务、查询订单等
4. 如果用户没有明确意图，可以询问用户想了解什么服务
5. 不超过150字"""

            # 使用LLM生成回复
            try:
                response_msg = self.llm_service.chat(context_prompt)
                print(f"[Agent] LLM response: {response_msg[:100]}...")
                state.set_topic(state.last_topic or "chat")
                
                # 记录助手回复
                state.add_message("assistant", response_msg)
                
                return {"type": "text", "message": response_msg}
            except Exception as llm_error:
                print(f"[Agent] LLM error: {llm_error}")
                # LLM失败时，不返回错误，而是尝试其他方式
                return {"type": "text", "message": "抱歉，服务暂时不可用。请稍后重试。"}

        except Exception as e:
            import traceback
            print(f"[Agent] Error: {e}")
            print(f"[Agent] Traceback: {traceback.format_exc()}")
            # 不再进入fallback，直接返回友好提示
            return {"type": "text", "message": "抱歉，处理您的请求时出现错误，请稍后重试。"}

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