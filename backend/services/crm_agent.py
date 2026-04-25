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
        auth_data = {"phone": phone, "auth_type": auth_type, "password": password}
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

    async def get_order_offers(self, customer_id: str, keyword: str = None) -> Dict:
        payload = {"custId": customer_id}
        if keyword:
            payload["prodOfferNameOrBrandName"] = keyword
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/order/offers",
            json=payload,
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

    async def query_customer_accounts(self, cust_id: str) -> Dict:
        """查询客户账户信息"""
        try:
            resp = self._session.post(
                f"{self.base_url}/CCInter/open/cust/accounts",
                json={"custId": cust_id},
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"[APIClient] query_customer_accounts error: status={resp.status_code}")
                return {"code": "-1", "message": f"HTTP error: {resp.status_code}", "resultObj": None}
        except Exception as e:
            print(f"[APIClient] query_customer_accounts exception: {e}")
            return {"code": "-1", "message": str(e), "resultObj": None}

    async def query_offer_members(self, prod_offer_id: int, prod_list: List[Dict] = None) -> Dict:
        """查询销售品成员配置"""
        payload = {"prodOfferId": prod_offer_id}
        if prod_list:
            payload["prodOfferList"] = prod_list
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/offer/members",
            json=payload,
            timeout=30
        )
        return resp.json()

    async def query_service_numbers(self, project_code: int, access_type: int) -> Dict:
        """查询可选号码"""
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/offer/serviceNo",
            json={"projectCode": project_code, "accessType": access_type},
            timeout=30
        )
        return resp.json()

    async def query_resources(self, category_id: str = "CS10002", life_status: str = "1") -> Dict:
        """查询ICCID资源"""
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/resource/query",
            json={"rootCategoryId": "CS10000", "categoryId": category_id, "lifeStatus": life_status},
            timeout=30
        )
        return resp.json()

    async def submit_order(self, order_data: Dict) -> Dict:
        """提交订单"""
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/order/submit",
            json=order_data,
            timeout=30
        )
        return resp.json()

    async def query_order_fee(self, fee_data: Dict) -> Dict:
        """查询订单费用/报价"""
        resp = self._session.post(
            f"{self.base_url}/CCInter/open/order/fee/query",
            json=fee_data,
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

# 流程步骤常量
FLOW_STEPS = {
    "OFFER_SELECT": "offer_select",        # 1. 选择主销售品
    "OPTGROUP_SELECT": "optgroup_select",  # 2. 选择附属销售品
    "SELECT_MEMBER": "select_member",      # 3. 选择成员
    "ACCOUNT_INFO": "account_info",       # 4. 选择账户
    "SELECT_NUMBER_COUNT": "select_number_count",  # 5. 询问订购号码数量
    "SELECT_NUMBER": "select_number",    # 6. 选号
    "SELECT_ICCID": "select_iccid",      # 7. 选ICCID
    "FEE_QUERY": "fee_query",             # 8. 费用查询/报价
    "FEE_CONFIRM": "fee_confirm",        # 9. 费用确认
    "SUBMIT": "submit",                 # 10. 提交订单
    "COMPLETE": "complete",              # 11. 竣工完成
}

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
            "step": None,           # 当前流程步骤
            "target_offer": None,    # 用户选中的主套餐
            "opt_groups": [],       # 附属销售品组
            "selected_main_plan": None,  # mainPricePlanPack选择
            "selected_invoice": None,     # invoicePack选择
            "pending_question": None,      # 待确认的问题
            "last_offer_list": [],         # 上次推荐的套餐列表
            "clarification_needed": None,  # 待澄清的问题
            "order_info": {},              # 订单信息
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
                
                # 如果没有offers，自动查询已订购销售品
                if not offers_list and cust_id:
                    offers_result = self.api_client.query_customer_offers(cust_id)
                    if offers_result.get("code") == "0":
                        offers_list = offers_result.get("resultObj", {}).get("list", [])
                
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
                    },
                    "offers": offers_list
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
- 我的套餐：用户问"我订了什么"、"我有哪些套餐"、"我现在的套餐"、"查一下我名下的套餐"这类
- 咨询问题：用户问规则、问费用、问怎么操作等
- 闲聊/其他：问候、闲聊、不会等

自然口语理解：
- "我流量不够用" → 推荐套餐（需要流量）
- "想便宜点" → 推荐套餐（需要性价比）
- "家里要宽带" → 推荐套餐（需要宽带）
- "能不能降套餐" → 办理业务（降套餐）
- "宽带怎么办" → 推荐套餐（需要宽带）
- "我现在的套餐是什么" → 我的套餐
- "我有哪些套餐" → 我的套餐
- "查一下我名下的套餐" → 我的套餐

结合上下文判断更准：
- 用户之前说过流量不够，这次问流量包 → 推荐套餐
- 用户之前说过想便宜，这次问便宜的 → 推荐套餐

只返回一个词（推荐套餐/办理业务/查询订单/我的套餐/咨询问题/其他）："""
            
            # 调用LLM判断意图
            print(f"[Agent] Calling LLM for intent check...")
            intent_decision = self.llm_service.invoke(intent_prompt)
            intent_text = intent_decision.content.strip().lower() if hasattr(intent_decision, 'content') else str(intent_decision).lower()

            print(f"[Agent] Intent check for '{message}': '{intent_text}'")
            print(f"[Agent] Authenticated: {state.authenticated}, CustomerID: {state.customer_id}")
            print(f"[Agent] Flow step: {state.get_flow_step()}")

            # 检查是否在订购流程中
            current_step = state.get_flow_step()

            # 步骤1：用户输入选择主销售品
            if current_step == FLOW_STEPS["OFFER_SELECT"]:
                offer_list = state.flow_context.get("offer_list", [])

                # 使用LLM理解用户选择意图
                selection_prompt = f"""用户回复：{message}
当前可选主销售品列表：
{self._format_offer_list(offer_list)}

请判断用户是否选择了某个主销售品。

选择判断规则：
1. 如果用户输入阿拉伯数字序号（如1、2、3），直接提取序号
2. 如果用户说"第一个"、"第二个"、"选择第X个"等，转换为对应序号
3. 如果用户说套餐名称包含关键字，匹配最相似的选项
4. 如果用户说"随便"、"都可以"、"无所谓"等，选择第一个选项
5. 如果用户明确拒绝或说"不需要"、"跳过"等，返回skip
6. 如果用户没有明确选择意图，返回none

只返回：序号数字、"skip"或"none" """

                selection_result = self.llm_service.invoke(selection_prompt)
                selection_text = selection_result.content.strip().lower() if hasattr(selection_result, 'content') else message.lower()

                if selection_text.isdigit():
                    idx = int(selection_text) - 1
                    if 0 <= idx < len(offer_list):
                        selected_offer = offer_list[idx]
                        offer_name = selected_offer.get("prodOfferName", "未知")
                        prod_offer_id = str(selected_offer.get("prodOfferId", ""))

                        print(f"[Agent] User selected main offer: {offer_name} (ID: {prod_offer_id})")

                        # 查询附属销售品
                        optgroup_result = await self.api_client.query_optgroup_offers(prod_offer_id)
                        opt_groups = optgroup_result.get("resultObj", [])

                        state.set_flow_step(FLOW_STEPS["OPTGROUP_SELECT"],
                            target_offer=selected_offer,
                            opt_groups=opt_groups
                        )

                        # 构建附属销售品列表
                        if opt_groups:
                            options_str = self._format_optgroup_list(opt_groups)
                            return {
                                "type": "order_select_optgroup",
                                "message": "您选择了【" + offer_name + "】！\n\n请选择附属销售品：\n\n" + options_str,
                                "opt_groups": opt_groups
                            }
                        else:
                            # 没有附属销售品，直接进入账户选择
                            return await self._go_to_account_selection(state, selected_offer)
                    else:
                        return {"type": "text", "message": "您选择的序号超出范围，请输入1-" + str(len(offer_list)) + "之间的数字~"}
                elif selection_text == "skip":
                    state.clear_flow()
                    return {"type": "text", "message": "好的，订购流程已取消。请问还有其他需要帮助的吗？"}
                else:
                    offer_list_str = self._format_offer_list(offer_list)
                    return {
                        "type": "text",
                        "message": "请从以下套餐中选择（输入序号或直接说套餐名称）：\n\n" + offer_list_str
                    }

            # 步骤2：用户输入选择附属销售品
            elif current_step == FLOW_STEPS["OPTGROUP_SELECT"]:
                opt_groups = state.flow_context.get("opt_groups", [])
                target_offer = state.flow_context.get("target_offer")

                if not opt_groups:
                    return await self._go_to_account_selection(state, target_offer)

                # 使用LLM理解用户选择意图
                selection_prompt = f"""用户回复：{message}
当前可选附属销售品列表：
{self._format_optgroup_list(opt_groups)}

请判断用户是否选择了某个附属销售品。

选择判断规则：
1. 如果用户输入阿拉伯数字序号（如1、2、3），直接提取序号
2. 如果用户说"第一个"、"第二个"、"选择第X个"等，转换为对应序号
3. 如果用户说套餐名称包含关键字，匹配最相似的选项
4. 如果用户说"随便"、"都可以"、"无所谓"等，选择第一个选项
5. 如果用户明确拒绝或说"不需要"、"跳过"等，返回skip
6. 如果用户没有明确选择意图，返回none

只返回：序号数字、"skip"或"none" """

                selection_result = self.llm_service.invoke(selection_prompt)
                selection_text = selection_result.content.strip().lower() if hasattr(selection_result, 'content') else message.lower()

                # 计算所有可选附属销售品的总数
                all_options = []
                for group in opt_groups:
                    for opt in group.get("optOfferList", []):
                        all_options.append(opt)

                # 解析LLM返回的选择
                if selection_text.isdigit():
                    idx = int(selection_text) - 1
                    if 0 <= idx < len(all_options):
                        selected_opt = all_options[idx]
                        print(f"[Agent] User selected optgroup: {selected_opt.get('prodOfferName')}")
                        
                        # 直接进入账户选择步骤
                        state.set_flow_step(FLOW_STEPS["ACCOUNT_INFO"],
                            target_offer=target_offer,
                            selected_opt=selected_opt
                        )
                        return await self._go_to_account_selection(state, target_offer, selected_opt)
                    else:
                        return {"type": "text", "message": "您选择的序号超出范围，请输入1-" + str(len(all_options)) + "之间的数字~"}
                elif selection_text == "skip":
                    # 跳过附属销售品，直接进入账户选择
                    state.set_flow_step(FLOW_STEPS["ACCOUNT_INFO"],
                        target_offer=target_offer,
                        selected_opt=None
                    )
                    return await self._go_to_account_selection(state, target_offer, None)
                else:
                    opt_list_str = self._format_optgroup_list(opt_groups)
                    return {
                        "type": "text",
                        "message": "请从以下附属销售品中选择（输入序号或直接说套餐名称）：\n\n" + opt_list_str
                    }

# 步骤3：成员配置（按顺序配置每个成员）
            elif current_step == FLOW_STEPS["SELECT_MEMBER"]:
                members = state.flow_context.get("members", [])
                target_offer = state.flow_context.get("target_offer")
                selected_opt = state.flow_context.get("selected_opt")
                selected_account = state.flow_context.get("selected_account")
                configured_members = state.flow_context.get("configured_members", [])
                current_member_idx = state.flow_context.get("current_member_idx", 0)

                if not members:
                    state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=[]
                    )
                    return await self._query_and_show_fee(state)

                if current_member_idx >= len(members):
                    state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=configured_members
                    )
                    return await self._query_and_show_fee(state)

                current_member = members[current_member_idx]
                member_name = current_member.get("prodOfferName", "未知")
                
                member_mobile_access = None
                member_cpe_access = None
                for access in current_member.get("accessTypeList", []):
                    atype = access.get("accessType")
                    if atype == "Mobile":
                        member_mobile_access = access
                    elif atype == "CPE":
                        member_cpe_access = access

                if member_mobile_access:
                    numbers_result = await self.api_client.query_service_numbers(
                        member_mobile_access.get("productId", 0),
                        member_mobile_access.get("accessTypeId", 0)
                    )
                    avail_numbers = numbers_result.get("resultObj", {}).get("availNumbers", [])
                    iccids_result = await self.api_client.query_resources()
                    iccids = iccids_result.get("resultObj", {}).get("list", [])
                    
                    if not avail_numbers:
                        configured_members.append(current_member)
                        if current_member_idx + 1 < len(members):
                            state.set_flow_step(FLOW_STEPS["SELECT_MEMBER"],
                                target_offer=target_offer,
                                selected_opt=selected_opt,
                                selected_account=selected_account,
                                members=members,
                                configured_members=configured_members,
                                current_member_idx=current_member_idx + 1
                            )
                            return {"type": "text", "message": f"成员【{member_name}】无可用号码，跳过..."}
                        else:
                            state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                                target_offer=target_offer,
                                selected_opt=selected_opt,
                                selected_account=selected_account,
                                members=configured_members
                            )
                            return await self._query_and_show_fee(state)
                    
                    state.set_flow_step(FLOW_STEPS["SELECT_NUMBER_COUNT"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=current_member_idx,
                        current_member=current_member,
                        avail_numbers=avail_numbers,
                        iccids=iccids,
                        member_mobile_access=member_mobile_access
                    )
                    
                    return {
                        "type": "select_number_count",
                        "message": f"📱 配置成员 {current_member_idx + 1}/{len(members)}：【{member_name}】\n\n该成员需要配置Mobile号码，请问您需要订购几个号码？\n\n（如：1个、2个、3个等）",
                        "avail_numbers_count": len(avail_numbers)
                    }
                elif member_cpe_access:
                    configured_members.append(current_member)
                    next_idx = current_member_idx + 1
                    
                    if next_idx < len(members):
                        next_member = members[next_idx]
                        next_name = next_member.get("prodOfferName", "未知")
                        state.set_flow_step(FLOW_STEPS["SELECT_MEMBER"],
                            target_offer=target_offer,
                            selected_opt=selected_opt,
                            selected_account=selected_account,
                            members=members,
                            configured_members=configured_members,
                            current_member_idx=next_idx
                        )
                        
                        access_types = []
                        for at in next_member.get("accessTypeList", []):
                            access_types.append(at.get("accessType", ""))
                        type_str = "、".join(access_types) if access_types else "未知"
                        
                        return {"type": "text", "message": f"✅ 成员【{member_name}】配置完成（CPE）\n\n继续配置 {next_idx + 1}/{len(members)}：【{next_name}】..."}
                    else:
                        state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                            target_offer=target_offer,
                            selected_opt=selected_opt,
                            selected_account=selected_account,
                            members=configured_members
                        )
                        return await self._query_and_show_fee(state)
                else:
                    configured_members.append(current_member)
                    next_idx = current_member_idx + 1
                    
                    if next_idx < len(members):
                        next_member = members[next_idx]
                        next_name = next_member.get("prodOfferName", "未知")
                        state.set_flow_step(FLOW_STEPS["SELECT_MEMBER"],
                            target_offer=target_offer,
                            selected_opt=selected_opt,
                            selected_account=selected_account,
                            members=members,
                            configured_members=configured_members,
                            current_member_idx=next_idx
                        )
                        return {"type": "text", "message": f"✅ 成员【{member_name}】配置完成\n\n继续配置 {next_idx + 1}/{len(members)}：【{next_name}】..."}
                    else:
                        state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                            target_offer=target_offer,
                            selected_opt=selected_opt,
                            selected_account=selected_account,
                            members=configured_members
                        )
                        return await self._query_and_show_fee(state)

            # 步骤4：账户选择 → 顺序配置成员 → 选号 → 选ICCID → 费用查询
            elif current_step == FLOW_STEPS["ACCOUNT_INFO"]:
                accounts = state.flow_context.get("accounts", [])
                members = state.flow_context.get("members", [])
                target_offer = state.flow_context.get("target_offer")
                selected_opt = state.flow_context.get("selected_opt")

                # 使用LLM理解用户账户选择意图
                selection_prompt = f"""用户回复：{message}
当前可选账户列表：
{self._format_account_list(accounts)}

请判断用户是否选择了某个账户。

选择判断规则：
1. 如果用户输入阿拉伯数字序号（如1、2、3），直接提取序号
2. 如果用户说"第一个"、"第二个"、"选择第X个"等，转换为对应序号
3. 如果用户说账户名称包含关键字，匹配最相似的选项
4. 如果用户说"随便"、"都可以"、"无所谓"等，选择第一个选项
5. 如果用户没有明确选择意图，返回none

只返回：序号数字或"none" """

                selection_result = self.llm_service.invoke(selection_prompt)
                selection_text = selection_result.content.strip().lower() if hasattr(selection_result, 'content') else message.lower()

                if selection_text.isdigit():
                    idx = int(selection_text) - 1
                    if 0 <= idx < len(accounts):
                        selected_account = accounts[idx]
                        
                        # 告知客户账户选择信息
                        account_name = selected_account.get("accountName", "未知")
                        pay_method = selected_account.get("payMethodText", "")
                        
                        # 如果有成员配置，检查是否有Mobile成员
                        if members:
                            # 检查是否有Mobile类型的成员
                            has_mobile_member = False
                            for member in members:
                                for access in member.get("accessTypeList", []):
                                    if access.get("accessType") == "Mobile":
                                        has_mobile_member = True
                                        break
                                if has_mobile_member:
                                    break
                            
                            if has_mobile_member:
                                # 进入号码数量询问步骤
                                first_member = members[0]
                                member_name = first_member.get("prodOfferName", "未知")
                                
                                # 检查第一个成员的accessType
                                first_mobile = None
                                for access in first_member.get("accessTypeList", []):
                                    if access.get("accessType") == "Mobile":
                                        first_mobile = access
                                        break
                                
                                if first_mobile:
                                    # 查询可选号码和ICCID
                                    numbers_result = await self.api_client.query_service_numbers(
                                        first_mobile.get("productId", 0),
                                        first_mobile.get("accessTypeId", 0)
                                    )
                                    avail_numbers = numbers_result.get("resultObj", {}).get("availNumbers", [])
                                    iccids_result = await self.api_client.query_resources()
                                    iccids = iccids_result.get("resultObj", {}).get("list", [])
                                    
                                    state.set_flow_step(FLOW_STEPS["SELECT_NUMBER_COUNT"],
                                        target_offer=target_offer,
                                        selected_opt=selected_opt,
                                        selected_account=selected_account,
                                        members=members,
                                        configured_members=[],
                                        current_member_idx=0,
                                        current_member=first_member,
                                        avail_numbers=avail_numbers,
                                        iccids=iccids,
                                        member_mobile_access=first_mobile
                                    )
                                    
                                    return {
                                        "type": "select_number_count",
                                        "message": f"✅ 账户已选择：【{account_name}】- {pay_method}\n\n📱 配置成员 1/{len(members)}：【{member_name}】\n\n该成员需要配置Mobile号码，请问您需要订购几个号码？\n\n（如：1个、2个、3个等）",
                                        "avail_numbers_count": len(avail_numbers)
                                    }
                            
                            # 没有Mobile成员，按顺序配置
                            state.set_flow_step(FLOW_STEPS["SELECT_MEMBER"],
                                target_offer=target_offer,
                                selected_opt=selected_opt,
                                selected_account=selected_account,
                                members=members,
                                configured_members=[],
                                current_member_idx=0
                            )
                            
                            first_member = members[0]
                            member_name = first_member.get("prodOfferName", "未知")
                            
                            first_mobile = None
                            first_cpe = None
                            for access in first_member.get("accessTypeList", []):
                                if access.get("accessType") == "Mobile":
                                    first_mobile = access
                                elif access.get("accessType") == "CPE":
                                    first_cpe = access
                            
                            if first_mobile:
                                numbers_result = await self.api_client.query_service_numbers(
                                    first_mobile.get("productId", 0),
                                    first_mobile.get("accessTypeId", 0)
                                )
                                avail_numbers = numbers_result.get("resultObj", {}).get("availNumbers", [])
                                iccids_result = await self.api_client.query_resources()
                                iccids = iccids_result.get("resultObj", {}).get("list", [])
                                
                                numbers_str = "\n".join([
                                    f"{i+1}. {num.get('code', '未知')}"
                                    for i, num in enumerate(avail_numbers[:15])
                                ]) if avail_numbers else "无可用号码"
                                
                                return {
                                    "type": "order_select_number",
                                    "message": f"✅ 账户已选择：【{account_name}】- {pay_method}\n\n📱 配置成员 1/{len(members)}：【{member_name}】\n\n请选择手机号码：\n" + numbers_str + "\n\n（输入序号选择）",
                                    "avail_numbers": avail_numbers,
                                    "iccids": iccids
                                }
                            elif first_cpe:
                                configured_members = [first_member]
                                if len(members) > 1:
                                    next_member = members[1]
                                    next_name = next_member.get("prodOfferName", "未知")
                                    return {
                                        "type": "text",
                                        "message": f"✅ 账户已选择：【{account_name}】- {pay_method}\n\n✅ 成员【{member_name}】配置完成（CPE）\n\n继续配置下一个成员：{next_name}..."
                                    }
                                else:
                                    state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                                        target_offer=target_offer,
                                        selected_opt=selected_opt,
                                        selected_account=selected_account,
                                        members=[first_member]
                                    )
                                    return await self._query_and_show_fee(state)
                            else:
                                configured_members = [first_member]
                                if len(members) > 1:
                                    return {
                                        "type": "text",
                                        "message": f"✅ 账户已选择：【{account_name}】- {pay_method}\n\n✅ 成员【{member_name}】配置完成\n\n继续配置下一个成员..."
                                    }
                                else:
                                    state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                                        target_offer=target_offer,
                                        selected_opt=selected_opt,
                                        selected_account=selected_account,
                                        members=configured_members
                                    )
                                    return await self._query_and_show_fee(state)
                    else:
                        return {"type": "text", "message": "您选择的序号超出范围，请输入1-" + str(len(accounts)) + "之间的数字~"}
                else:
                    accounts_str = self._format_account_list(accounts)
                    return {
                        "type": "text",
                        "message": "请从以下账户中选择（输入序号或直接说账户名称）：\n\n" + accounts_str
                    }

            # 步骤5：询问订购号码数量
            elif current_step == FLOW_STEPS["SELECT_NUMBER_COUNT"]:
                avail_numbers = state.flow_context.get("avail_numbers", [])
                iccids = state.flow_context.get("iccids", [])
                members = state.flow_context.get("members", [])
                configured_members = state.flow_context.get("configured_members", [])
                current_member_idx = state.flow_context.get("current_member_idx", 0)
                current_member = state.flow_context.get("current_member")
                target_offer = state.flow_context.get("target_offer")
                selected_account = state.flow_context.get("selected_account")
                selected_opt = state.flow_context.get("selected_opt")
                
                # 解析用户输入的数量
                count_match = re.search(r'(\d+)', message)
                if count_match:
                    number_count = int(count_match.group(1))
                    max_count = len(avail_numbers)
                    
                    if number_count > max_count:
                        return {
                            "type": "text",
                            "message": f"⚠️ 可用号码只有{max_count}个，请重新输入需要的数量（1-{max_count}）"
                        }
                    
                    numbers_str = "\n".join([
                        f"{i+1}. {num.get('code', '未知')}"
                        for i, num in enumerate(avail_numbers[:15])
                    ]) if avail_numbers else "无可用号码"
                    
                    state.set_flow_step(FLOW_STEPS["SELECT_NUMBER"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=current_member_idx,
                        current_member=current_member,
                        selected_numbers=[],
                        selected_iccids=[],
                        required_number_count=number_count,
                        avail_numbers=avail_numbers,
                        iccids=iccids
                    )
                    
                    return {
                        "type": "order_select_number",
                        "message": f"好的，您需要订购{number_count}个号码。\n\n请选择号码（可多选，用逗号分隔，如：1,2,3）：\n" + numbers_str,
                        "avail_numbers": avail_numbers,
                        "iccids": iccids,
                        "required_count": number_count
                    }
                else:
                    return {
                        "type": "text",
                        "message": f"请输入您需要订购的号码数量（当前可用号码：{len(avail_numbers)}个）"
                    }

            # 步骤6：选号（支持多选）
            elif current_step == FLOW_STEPS["SELECT_NUMBER"]:
                avail_numbers = state.flow_context.get("avail_numbers", [])
                iccids = state.flow_context.get("iccids", [])
                selected_numbers = state.flow_context.get("selected_numbers", [])
                selected_iccids = state.flow_context.get("selected_iccids", [])
                members = state.flow_context.get("members", [])
                configured_members = state.flow_context.get("configured_members", [])
                current_member_idx = state.flow_context.get("current_member_idx", 0)
                current_member = state.flow_context.get("current_member")
                target_offer = state.flow_context.get("target_offer")
                selected_account = state.flow_context.get("selected_account")
                selected_opt = state.flow_context.get("selected_opt")
                required_number_count = state.flow_context.get("required_number_count", 1)
                
                # 解析用户输入的序号（支持多选：1,2,3 或 1 2 3）
                numbers = re.findall(r'\d+', message)
                new_selected = []
                for num_str in numbers:
                    try:
                        idx = int(num_str) - 1
                        if 0 <= idx < len(avail_numbers):
                            new_selected.append(avail_numbers[idx])
                    except:
                        pass
                
                if not new_selected:
                    numbers_str = "\n".join([
                        f"{i+1}. {num.get('code', '未知')}"
                        for i, num in enumerate(avail_numbers[:15])
                    ]) if avail_numbers else "无可用号码"
                    return {
                        "type": "text",
                        "message": f"请选择手机号码（需选{required_number_count}个，可多选）：\n\n" + numbers_str
                    }
                
                selected_numbers = selected_numbers + new_selected
                unique_numbers = []
                seen = set()
                for n in selected_numbers:
                    code = n.get("code", "")
                    if code not in seen:
                        unique_numbers.append(n)
                        seen.add(code)
                selected_numbers = unique_numbers
                
                nums_selected_str = ", ".join([n.get("code", "") for n in selected_numbers])
                
                # 检查选中的数量是否符合要求
                if len(selected_numbers) < required_number_count:
                    numbers_str = "\n".join([
                        f"{i+1}. {num.get('code', '未知')}"
                        for i, num in enumerate(avail_numbers[:15])
                    ]) if avail_numbers else "无可用号码"
                    
                    state.set_flow_step(FLOW_STEPS["SELECT_NUMBER"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=current_member_idx,
                        current_member=current_member,
                        selected_numbers=selected_numbers,
                        selected_iccids=selected_iccids,
                        required_number_count=required_number_count,
                        avail_numbers=avail_numbers,
                        iccids=iccids
                    )
                    
                    return {
                        "type": "text",
                        "message": f"⚠️ 已选{len(selected_numbers)}个号码，还需要{required_number_count - len(selected_numbers)}个。\n\n请继续选择：\n" + numbers_str
                    }
                
                # 数量满足要求，进入选ICCID（直接使用号码数量）
                iccids_str = "\n".join([
                    f"{i+1}. {res.get('simInfo', {}).get('iccid', '未知')} - {res.get('simInfo', {}).get('cardType', '未知')}"
                    for i, res in enumerate(iccids[:15])
                ]) if iccids else "无可用ICCID"
                
                state.set_flow_step(FLOW_STEPS["SELECT_ICCID"],
                    target_offer=target_offer,
                    selected_opt=selected_opt,
                    selected_account=selected_account,
                    members=members,
                    configured_members=configured_members,
                    current_member_idx=current_member_idx,
                    current_member=current_member,
                    selected_numbers=selected_numbers,
                    selected_iccids=[],
                    required_number_count=required_number_count,
                    avail_numbers=avail_numbers,
                    iccids=iccids
                )
                
                return {
                    "type": "order_select_iccid",
                    "message": f"✅ 已选号码（{len(selected_numbers)}个）：{nums_selected_str}\n\n请选择{len(selected_numbers)}个ICCID（用逗号分隔，如：1,2,3）：\n" + iccids_str,
                    "iccids": iccids,
                    "required_count": len(selected_numbers)
                }

            # 步骤7：选ICCID（支持多选）
            elif current_step == FLOW_STEPS["SELECT_ICCID"]:
                iccids = state.flow_context.get("iccids", [])
                selected_numbers = state.flow_context.get("selected_numbers", [])
                selected_iccids = state.flow_context.get("selected_iccids", [])
                members = state.flow_context.get("members", [])
                configured_members = state.flow_context.get("configured_members", [])
                current_member_idx = state.flow_context.get("current_member_idx", 0)
                current_member = state.flow_context.get("current_member")
                target_offer = state.flow_context.get("target_offer")
                selected_account = state.flow_context.get("selected_account")
                selected_opt = state.flow_context.get("selected_opt")
                required_iccid_count = state.flow_context.get("required_iccid_count", len(selected_numbers))
                
                iccid_indices = re.findall(r'\d+', message)
                new_iccids = []
                for idx_str in iccid_indices:
                    try:
                        idx = int(idx_str) - 1
                        if 0 <= idx < len(iccids):
                            new_iccids.append(iccids[idx])
                    except:
                        pass
                
                if not new_iccids:
                    iccids_str = "\n".join([
                        f"{i+1}. {res.get('simInfo', {}).get('iccid', '未知')} - {res.get('simInfo', {}).get('cardType', '未知')}"
                        for i, res in enumerate(iccids[:15])
                    ]) if iccids else "无可用ICCID"
                    return {
                        "type": "text",
                        "message": f"请选择ICCID（需���{required_iccid_count}个）：\n\n" + iccids_str
                    }
                
                selected_iccids = selected_iccids + new_iccids
                
                if len(selected_iccids) < required_iccid_count:
                    iccids_str = "\n".join([
                        f"{i+1}. {res.get('simInfo', {}).get('iccid', '未知')} - {res.get('simInfo', {}).get('cardType', '未知')}"
                        for i, res in enumerate(iccids[:15])
                    ]) if iccids else "无可用ICCID"
                    
                    state.set_flow_step(FLOW_STEPS["SELECT_ICCID"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=current_member_idx,
                        current_member=current_member,
                        selected_numbers=selected_numbers,
                        selected_iccids=selected_iccids,
                        required_iccid_count=required_iccid_count,
                        avail_numbers=avail_numbers,
                        iccids=iccids
                    )
                    
                    return {
                        "type": "text",
                        "message": f"⚠️ 已选{len(selected_iccids)}个ICCID，还需要{required_iccid_count - len(selected_iccids)}个\n\n请继续选择：\n" + iccids_str
                    }
                
                unique_iccids = []
                seen = set()
                for i in selected_iccids:
                    iccid = i.get("simInfo", {}).get("iccid", "")
                    if iccid not in seen:
                        unique_iccids.append(i)
                        seen.add(iccid)
                selected_iccids = unique_iccids[:required_iccid_count]
                
                member_info = current_member.copy() if current_member else {}
                member_info["selected_numbers"] = selected_numbers
                member_info["selected_iccids"] = selected_iccids
                configured_members.append(member_info)
                
                next_idx = current_member_idx + 1
                
                if next_idx < len(members):
                    next_member = members[next_idx]
                    next_name = next_member.get("prodOfferName", "未知")
                    state.set_flow_step(FLOW_STEPS["SELECT_MEMBER"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=next_idx
                    )
                    return {"type": "text", "message": f"✅ 成员【{current_member.get('prodOfferName', '未知')}】配置完成（{len(selected_numbers)}个号码）\n\n继续配置 {next_idx + 1}/{len(members)}：【{next_name}】..."}
                else:
                    state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=configured_members
                    )
                    return await self._query_and_show_fee(state)
                iccids = state.flow_context.get("iccids", [])
                selected_numbers = state.flow_context.get("selected_numbers", [])
                selected_iccids = state.flow_context.get("selected_iccids", [])
                members = state.flow_context.get("members", [])
                configured_members = state.flow_context.get("configured_members", [])
                current_member_idx = state.flow_context.get("current_member_idx", 0)
                current_member = state.flow_context.get("current_member")
                target_offer = state.flow_context.get("target_offer")
                selected_account = state.flow_context.get("selected_account")
                selected_opt = state.flow_context.get("selected_opt")
                
                required_count = len(selected_numbers)
                
                iccid_indices = re.findall(r'\d+', message)
                new_iccids = []
                for idx_str in iccid_indices:
                    try:
                        idx = int(idx_str) - 1
                        if 0 <= idx < len(iccids):
                            new_iccids.append(iccids[idx])
                    except:
                        pass
                
                if not new_iccids:
                    iccids_str = "\n".join([
                        f"{i+1}. {res.get('simInfo', {}).get('iccid', '未知')} - {res.get('simInfo', {}).get('cardType', '未知')}"
                        for i, res in enumerate(iccids[:15])
                    ]) if iccids else "无可用ICCID"
                    return {
                        "type": "text",
                        "message": f"请选择ICCID（需选{required_count}个，输入序号用逗号分隔）：\n\n" + iccids_str
                    }
                
                selected_iccids = selected_iccids + new_iccids
                
                if len(selected_iccids) < required_count:
                    iccids_str = "\n".join([
                        f"{i+1}. {res.get('simInfo', {}).get('iccid', '未知')} - {res.get('simInfo', {}).get('cardType', '未知')}"
                        for i, res in enumerate(iccids[:15])
                    ]) if iccids else "无可用ICCID"
                    
                    state.set_flow_step(FLOW_STEPS["SELECT_ICCID"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=current_member_idx,
                        current_member=current_member,
                        selected_numbers=selected_numbers,
                        selected_iccids=selected_iccids,
                        avail_numbers=[],
                        iccids=iccids
                    )
                    
                    return {
                        "type": "text",
                        "message": f"⚠️ 已选{len(selected_iccids)}个ICCID，还需再选{required_count - len(selected_iccids)}个\n\n请继续选择：\n" + iccids_str
                    }
                
                unique_iccids = []
                seen = set()
                for i in selected_iccids:
                    iccid = i.get("simInfo", {}).get("iccid", "")
                    if iccid not in seen:
                        unique_iccids.append(i)
                        seen.add(iccid)
                selected_iccids = unique_iccids[:required_count]
                
                member_info = current_member.copy() if current_member else {}
                member_info["selected_numbers"] = selected_numbers
                member_info["selected_iccids"] = selected_iccids
                configured_members.append(member_info)
                
                next_idx = current_member_idx + 1
                
                if next_idx < len(members):
                    next_member = members[next_idx]
                    next_name = next_member.get("prodOfferName", "未知")
                    state.set_flow_step(FLOW_STEPS["SELECT_MEMBER"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=members,
                        configured_members=configured_members,
                        current_member_idx=next_idx
                    )
                    return {"type": "text", "message": f"✅ 成员【{current_member.get('prodOfferName', '未知')}】配置完成（{len(selected_numbers)}个号码）\n\n继续配置 {next_idx + 1}/{len(members)}：【{next_name}】..."}
                else:
                    state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                        target_offer=target_offer,
                        selected_opt=selected_opt,
                        selected_account=selected_account,
                        members=configured_members
                    )
                    return await self._query_and_show_fee(state)

                if selection_text.isdigit():
                    idx = int(selection_text) - 1
                    if 0 <= idx < len(iccids):
                        selected_iccid = iccids[idx]
                        state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                            selected_iccid=selected_iccid
                        )

                        # 构建费用查询报文
                        basic_offers = []
                        for member in members:
                            for access in member.get("accessTypeList", []):
                                if access.get("accessType") == "Mobile":
                                    basic_offers.append({
                                        "offerId": access.get("prodOfferId", 600002903),
                                        "offerType": 1,
                                        "productId": access.get("productId", 100002902),
                                        "offerServiceOfferId": 100060101,
                                        "serviceOfferId": 2101,
                                        "billingNo": selected_number.get("code", "13800000000") if selected_number else "13800000000",
                                        "accessType": access.get("accessTypeId", 811),
                                        "iccid": selected_iccid.get("simInfo", {}).get("iccid", "") if selected_iccid else "",
                                        "imsi": selected_iccid.get("simInfo", {}).get("imsi", "") if selected_iccid else "",
                                        "actionCd": "5101",
                                        "prodActionCd": "101",
                                        "profitCenter": "0",
                                        "optOffers": [],
                                        "serviceRegionId": "1"
                                    })
                                elif access.get("accessType") == "CPE":
                                    basic_offers.append({
                                        "offerId": access.get("prodOfferId", 609615487),
                                        "offerType": 1,
                                        "productId": access.get("productId", 100000004),
                                        "offerServiceOfferId": 100060051,
                                        "serviceOfferId": 4101,
                                        "billingNo": "20110000242",
                                        "accessType": access.get("accessTypeId", 830),
                                        "actionCd": "5101",
                                        "prodActionCd": "101",
                                        "profitCenter": "0",
                                        "optOffers": [],
                                        "serviceRegionId": "1"
                                    })

                        pkg_offer = {
                            "offerId": target_offer.get("prodOfferId", 600000004) if target_offer else 600000004,
                            "offerServiceOfferId": 100000561,
                            "exprieTime": 10000,
                            "durationUnit": 2,
                            "actionCd": 5101,
                            "offerType": 2,
                            "offerSaleType": "I",
                            "optOffers": [],
                            "serviceRegionId": "1",
                            "paymentType": "1",
                            "accountId": selected_account.get("accountId") if selected_account else "120020"
                        }

                        fee_data = {
                            "custId": state.customer_id,
                            "basicOffers": basic_offers,
                            "pkgOffer": pkg_offer,
                            "accountId": selected_account.get("accountId") if selected_account else "120020",
                            "serviceRegionId": "1",
                            "contractCd": None,
                            "tariffUnitId": "1031"
                        }

                        fee_result = await self.api_client.query_order_fee(fee_data)

                        if fee_result.get("code") == "0":
                            fee_info = fee_result.get("resultObj", {})
                            fee_items = fee_info.get("feeItemDetailList", [])
                            total_fee = float(fee_info.get("totalFee", "0"))

                            # 存储费用信息
                            state.set_flow_step(FLOW_STEPS["FEE_CONFIRM"],
                                fee_data=fee_data,
                                fee_items=fee_items,
                                total_fee=total_fee
                            )

                            # 格式化费用明细
                            fee_lines = []
                            for item in fee_items:
                                fee_name = item.get("feeItemName", "")
                                fee_amount = item.get("totalFee", "0")
                                fee_lines.append(f"• {fee_name}：{fee_amount}元")

                            fee_summary = "\n".join(fee_lines)

                            return {
                                "type": "order_fee_confirm",
                                "message": "📋 费用明细如下：\n\n" + fee_summary + "\n\n合计：" + str(total_fee) + "元\n\n请确认是否办理？（回复\"确认\"或\"好的\"办理，其他回复取消）",
                                "fee_items": fee_items,
                                "total_fee": total_fee
                            }
                        else:
                            return {
                                "type": "order_failed",
                                "message": "❌ 查询费用失败：" + fee_result.get('message', '未知错误')
                            }
                    else:
                        return {"type": "text", "message": "您选择的序号超出范围，请输入1-" + str(len(iccids)) + "之间的数字~"}
                else:
                    iccids_str = self._format_iccid_list(iccids)
                    return {
                        "type": "text",
                        "message": "请从以下ICCID中选择（输入序号）：\n\n" + iccids_str
                    }

            # 步骤6：费用确认
            elif current_step == FLOW_STEPS["FEE_CONFIRM"]:
                # 使用LLM判断用户是否确认
                confirm_prompt = f"""用户回复：{message}

请判断用户是否确认办理业务。

确认判断规则：
1. 如果用户说"确认"、"好的"、"办理"、"可以"、"是的"等，确认办理
2. 如果用户说"取消"、"算了"、"不要了"、"不办了"等，取消办理
3. 其他回复视为未明确确认

只返回："confirm"或"cancel" """

                confirm_result = self.llm_service.invoke(confirm_prompt)
                confirm_text = confirm_result.content.strip().lower() if hasattr(confirm_result, 'content') else message.lower()

                if "cancel" in confirm_text:
                    state.clear_flow()
                    return {"type": "text", "message": "好的，订购流程已取消。请问还有其他需要帮助的吗？"}

                if "confirm" not in confirm_text:
                    return {
                        "type": "text",
                        "message": "请确认是否办理？（回复\"确认\"或\"好的\"办理，其他回复取消）"
                    }

                # 用户确认，执行提交
                fee_data = state.flow_context.get("fee_data", {})
                target_offer = state.flow_context.get("target_offer")
                selected_account = state.flow_context.get("selected_account")

                # 组装订单数据
                order_data = {
                    "custId": state.customer_id,
                    "custName": state.customer_name or "客户",
                    "contactPeople": state.customer_name or "客户",
                    "contactPhone": state.phone or "13800000000",
                    "channelId": 1,
                    "staffId": "SUBE01",
                    "beId": "98d2186f6a6f407888457215cdd61c28",
                    "accountId": selected_account.get("accountId") if selected_account else "120020",
                    "serviceRegionId": "1",
                    "contractCd": None,
                    "tariffUnitId": "1031",
                    "pkgOffer": fee_data.get("pkgOffer", {}),
                    "basicOffers": fee_data.get("basicOffers", []),
                    "hybirdInfo": {"hybirdSubscribeFlag": False, "defaultAcct": "2", "preAccountName": ""}
                }

                submit_result = await self.api_client.submit_order(order_data)

                if submit_result.get("code") == "0":
                    order_result = submit_result.get("resultObj", {})
                    order_id = order_result.get("custOrderId", "未知")
                    fees = order_result.get("feeItemDetailList", [])
                    total_fee = sum(float(f.get("totalFee", "0")) for f in fees)
                    state.clear_flow()

                    msg = "✅ 订单提交成功！\n\n"
                    if target_offer:
                        msg += "套餐：" + target_offer.get("prodOfferName", "") + "\n"
                    if state.flow_context.get("selected_number"):
                        msg += "号码：" + state.flow_context.get("selected_number").get("code", "") + "\n"
                    msg += "\n订单号：" + order_id + "\n费用：" + str(total_fee) + "元\n\n预计稍后生效，有问题随时找我哦~"

                    return {
                        "type": "order_success",
                        "message": msg,
                        "order_id": order_id
                    }
                else:
                    return {
                        "type": "order_failed",
                        "message": "❌ 订单提交失败：" + submit_result.get('message', '未知错误')
                    }

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
                    return {"type": "text", "message": f"亲，查询订单需要先登录验证一下哦~ 输入手机号和密码登录（手机号 空格 密码）就可以啦"}

            # 我的套餐 - 查询已订购销售品
            elif "我的套餐" in intent_text:
                # 检查登录状态
                if not state.authenticated:
                    return {"type": "auth_required", "message": "查询套餐需要先登录验证身份哦~\n\n请输入：手机号码 密码（如：13800138000 123456）"}
                
                # 查询客户已订购的销售品
                if state.customer_id:
                    offers_result = self.api_client.query_customer_offers(state.customer_id)
                    if offers_result.get("code") == "0":
                        offers_list = offers_result.get("resultObj", {}).get("list", [])
                        offers_msg = format_offers_for_language(offers_list, language)
                        
                        state.add_message("assistant", offers_msg)
                        return {"type": "text", "message": f"📋 您名下已订购的套餐信息：\n\n{offers_msg}\n\n{trans['dear_user']}，请问还有什么可以帮到您的？"}
                    else:
                        return {"type": "text", "message": "暂时无法查询到您的套餐信息，请稍后再试~"}
                else:
                    return {"type": "text", "message": "登录信息已失效，请重新登录后再查询套餐~"}

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

# 办理业务
            elif "办理业务" in intent_text:
                # 检查登录状态
                if not state.authenticated:
                    return {"type": "auth_required", "message": "办理业务需要先登录验证身份哦~\n\n请输入：手机号码 密码（如：13800138000 123456）"}

                current_step = state.get_flow_step()
                print(f"[Agent] Ordering flow step: {current_step}")

                # 步骤1：选择主销售品
                if current_step is None or current_step == FLOW_STEPS["OFFER_SELECT"]:
                    # 使用LLM从消息中提取客户对套餐的描述/关键词
                    keyword_extraction_prompt = f"""从用户消息中提取套餐相关的关键词或描述。
用户消息：{message}

请提取：
- 用户提到的套餐名称、品牌、类型（如5G、宽带、家庭等）
- 如果用户没有提到任何套餐相关词，返回空字符串

只返回提取的关键词，不要其他解释。如果没有提取到，返回"无"："""

                    keyword_result = self.llm_service.invoke(keyword_extraction_prompt)
                    keyword_text = keyword_result.content.strip() if hasattr(keyword_result, 'content') else ""
                    
                    # 如果提取到有效关键词，过滤掉"无"等无效词
                    keyword = None
                    if keyword_text and keyword_text.lower() not in ["无", "没有", "暂无", "空", "none", ""]:
                        keyword = keyword_text
                    
                    print(f"[Agent] Extracted keyword: {keyword}")
                    
                    # 调用 /CCInter/open/order/offers 查询可订购销售品
                    offers_result = await self.api_client.get_order_offers(state.customer_id, keyword)
                    if offers_result.get("code") == "0":
                        offer_list = offers_result.get("resultObj", {}).get("list", [])

                        if not offer_list:
                            if keyword:
                                return {"type": "text", "message": f"暂未找到与\"{keyword}\"相关的套餐，请问是否有其他偏好？"}
                            else:
                                return {"type": "text", "message": "暂无可订购的套餐"}

                        # 如果没有指定套餐关键词，查询每个主销售品的附属销售品
                        offer_with_optgroups = []
                        if not keyword:
                            for offer in offer_list:
                                prod_offer_id = str(offer.get("prodOfferId", ""))
                                optgroup_result = await self.api_client.query_optgroup_offers(prod_offer_id)
                                opt_groups = optgroup_result.get("resultObj", [])
                                offer_with_optgroups.append({
                                    "offer": offer,
                                    "opt_groups": opt_groups
                                })
                        else:
                            # 有关键词时，只展示主销售品信息
                            for offer in offer_list:
                                offer_with_optgroups.append({
                                    "offer": offer,
                                    "opt_groups": []
                                })

                        # 构建带序号的列表，展示主销售品描述和附属销售品信息
                        offer_lines = []
                        for i, item in enumerate(offer_with_optgroups):
                            offer = item["offer"]
                            opt_groups = item["opt_groups"]
                            
                            offer_name = offer.get("prodOfferName", "未知")
                            offer_desc = offer.get("offerDescription", "")
                            offer_fee = offer.get("offerFeeDescription", "")
                            
                            offer_lines.append(f"【{i+1}】{offer_name}")
                            if offer_desc:
                                offer_lines.append(f"    描述：{offer_desc}")
                            if offer_fee:
                                offer_lines.append(f"    费用：{offer_fee}")
                            
                            # 展示附属销售品信息
                            if opt_groups:
                                for group in opt_groups:
                                    group_name = group.get("optGroupName", "")
                                    opt_list = group.get("optOfferList", [])
                                    if opt_list:
                                        opt_names = "、".join([o.get("prodOfferName", "")[:10] for o in opt_list[:3]])
                                        if len(opt_list) > 3:
                                            opt_names += f"等{len(opt_list)}个"
                                        offer_lines.append(f"    {group_name}：{opt_names}")
                            else:
                                offer_lines.append(f"    附属销售品：待选择后查看")
                            
                            offer_lines.append("")

                        offers_str = "\n".join(offer_lines) if offer_lines else "暂无可订购套餐"

                        state.set_flow_step(FLOW_STEPS["OFFER_SELECT"], 
                            offer_list=offer_list,
                            offer_with_optgroups=offer_with_optgroups
                        )
                        return {
                            "type": "order_select_offer",
                            "message": "请选择您要订购的主销售品：\n\n" + offers_str + "\n（输入序号，如：1、2、3）",
                            "offers": offer_list
                        }
                    else:
                        return {"type": "text", "message": "暂无可订购的套餐"}

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

    async def _go_to_account_selection(self, state: CRMState, target_offer: Dict, selected_opt: Dict = None, selected_member: Dict = None) -> Dict:
        """进入账户选择步骤"""
        # 查询客户账户信息
        accounts_result = await self.api_client.query_customer_accounts(state.customer_id)
        accounts = accounts_result.get("resultObj", {}).get("list", [])

        # 如果已选择成员，使用selected_member；否则查询成员
        if selected_member:
            members = [selected_member]
        else:
            members_result = await self.api_client.query_offer_members(target_offer.get("prodOfferId", 0))
            members = members_result.get("resultObj", [])

        # 检查是否有Mobile类型的成员
        has_mobile = False
        mobile_member = None
        for member in members:
            for access in member.get("accessTypeList", []):
                if access.get("accessType") == "Mobile":
                    has_mobile = True
                    mobile_member = member
                    break
            if has_mobile:
                break

        # 查询可选号码
        avail_numbers = []
        iccids = []
        if has_mobile:
            for member in members:
                for access in member.get("accessTypeList", []):
                    if access.get("accessType") == "Mobile":
                        numbers_result = await self.api_client.query_service_numbers(
                            access.get("productId", 0),
                            access.get("accessTypeId", 0)
                        )
                        avail_numbers = numbers_result.get("resultObj", {}).get("availNumbers", [])
                        break

            # 查询ICCID
            iccids_result = await self.api_client.query_resources()
            iccids = iccids_result.get("resultObj", {}).get("list", [])

        accounts_str = "\n".join([
            f"{i+1}. {acc.get('accountName', '未知')} - {acc.get('payMethodText', '')}"
            for i, acc in enumerate(accounts)
        ]) if accounts else "系统默认账户"

        # 如果没有Mobile成员，直接进入费用查询
        if not has_mobile:
            state.set_flow_step(FLOW_STEPS["FEE_QUERY"],
                accounts=accounts,
                target_offer=target_offer,
                selected_opt=selected_opt,
                selected_account=accounts[0] if accounts else None,
                members=members
            )
            # 查询费用
            return await self._query_and_show_fee(state)
        else:
            state.set_flow_step(FLOW_STEPS["ACCOUNT_INFO"],
                accounts=accounts,
                members=members,
                avail_numbers=avail_numbers,
                iccids=iccids,
                target_offer=target_offer,
                selected_opt=selected_opt
            )

            return {
                "type": "order_select_account",
                "message": "请选择支付账户：\n\n" + accounts_str + "\n\n（输入序号选择）",
                "accounts": accounts,
                "members": members,
                "avail_numbers": avail_numbers,
                "iccids": iccids
            }

    async def _query_and_show_fee(self, state: CRMState) -> Dict:
        """查询并展示费用"""
        target_offer = state.flow_context.get("target_offer")
        selected_account = state.flow_context.get("selected_account")
        selected_opt = state.flow_context.get("selected_opt")
        members = state.flow_context.get("members", [])

        # 构建费用查询报文
        basic_offers = []
        for member in members:
            for access in member.get("accessTypeList", []):
                if access.get("accessType") == "CPE":
                    basic_offers.append({
                        "offerId": access.get("prodOfferId", 609615487),
                        "offerType": 1,
                        "productId": access.get("productId", 100000004),
                        "offerServiceOfferId": 100060051,
                        "serviceOfferId": 4101,
                        "billingNo": "20110000242",
                        "accessType": access.get("accessTypeId", 830),
                        "actionCd": "5101",
                        "prodActionCd": "101",
                        "profitCenter": "0",
                        "optOffers": [],
                        "serviceRegionId": "1"
                    })

        pkg_offer = {
            "offerId": target_offer.get("prodOfferId", 600000004) if target_offer else 600000004,
            "offerServiceOfferId": 100000561,
            "exprieTime": 10000,
            "durationUnit": 2,
            "actionCd": 5101,
            "offerType": 2,
            "offerSaleType": "I",
            "optOffers": [],
            "serviceRegionId": "1",
            "paymentType": "1",
            "accountId": selected_account.get("accountId") if selected_account else "120020"
        }

        fee_data = {
            "custId": state.customer_id,
            "basicOffers": basic_offers,
            "pkgOffer": pkg_offer,
            "accountId": selected_account.get("accountId") if selected_account else "120020",
            "serviceRegionId": "1",
            "contractCd": None,
            "tariffUnitId": "1031"
        }

        fee_result = await self.api_client.query_order_fee(fee_data)

        if fee_result.get("code") == "0":
            fee_info = fee_result.get("resultObj", {})
            fee_items = fee_info.get("feeItemDetailList", [])
            total_fee = float(fee_info.get("totalFee", "0"))

            state.set_flow_step(FLOW_STEPS["FEE_CONFIRM"],
                fee_data=fee_data,
                fee_items=fee_items,
                total_fee=total_fee
            )

            fee_lines = []
            for item in fee_items:
                fee_name = item.get("feeItemName", "")
                fee_amount = item.get("totalFee", "0")
                fee_lines.append("• " + fee_name + "：" + fee_amount + "元")

            fee_summary = "\n".join(fee_lines)

            return {
                "type": "order_fee_confirm",
                "message": "📋 费用明细如下：\n\n" + fee_summary + "\n\n合计：" + str(total_fee) + "元\n\n请确认是否办理？（回复\"确认\"或\"好的\"办理，其他回复取消）",
                "fee_items": fee_items,
                "total_fee": total_fee
            }
        else:
            return {
                "type": "order_failed",
                "message": "❌ 查询费用失败：" + fee_result.get('message', '未知错误')
            }

    async def _submit_order(self, state: CRMState) -> Dict:
        """提交订单（直接提交，不查询费用）"""
        target_offer = state.flow_context.get("target_offer")
        selected_account = state.flow_context.get("selected_account")
        fee_data = state.flow_context.get("fee_data", {})

        order_data = {
            "custId": state.customer_id,
            "custName": state.customer_name or "客户",
            "contactPeople": state.customer_name or "客户",
            "contactPhone": state.phone or "13800000000",
            "channelId": 1,
            "staffId": "SUBE01",
            "beId": "98d2186f6a6f407888457215cdd61c28",
            "accountId": selected_account.get("accountId") if selected_account else "120020",
            "serviceRegionId": "1",
            "contractCd": None,
            "tariffUnitId": "1031",
            "pkgOffer": fee_data.get("pkgOffer", {}),
            "basicOffers": fee_data.get("basicOffers", []),
            "hybirdInfo": {"hybirdSubscribeFlag": False, "defaultAcct": "2", "preAccountName": ""}
        }

        submit_result = await self.api_client.submit_order(order_data)

        if submit_result.get("code") == "0":
            order_result = submit_result.get("resultObj", {})
            order_id = order_result.get("custOrderId", "未知")
            fees = order_result.get("feeItemDetailList", [])
            total_fee = sum(float(f.get("totalFee", "0")) for f in fees)
            state.clear_flow()

            msg = "✅ 订单提交成功！\n\n"
            if target_offer:
                msg += "套餐：" + target_offer.get("prodOfferName", "") + "\n"
            msg += "\n订单号：" + order_id + "\n费用：" + str(total_fee) + "元\n\n预计稍后生效，有问题随时找我哦~"

            return {
                "type": "order_success",
                "message": msg,
                "order_id": order_id
            }
        else:
            return {
                "type": "order_failed",
                "message": "❌ 订单提交失败：" + submit_result.get('message', '未知错误')
            }

    def _format_fee_list(self, fee_items: List[Dict]) -> str:
        """格式化费用明细列表"""
        lines = []
        for item in fee_items:
            fee_name = item.get("feeItemName", "未知费用")
            fee_amount = item.get("totalFee", "0")
            lines.append("• " + fee_name + "：" + fee_amount + "元")
        return "\n".join(lines) if lines else "暂无费用明细"

    def _format_optgroup_list(self, opt_groups: List[Dict]) -> str:
        """格式化附属销售品列表"""
        lines = []
        for group in opt_groups:
            group_name = group.get("optGroupName", "")
            offers_in_group = group.get("optOfferList", [])
            for i, opt in enumerate(offers_in_group[:10]):
                opt_name = opt.get("prodOfferName", "未知")
                opt_desc = opt.get("offerDescription", "")
                lines.append(f"{len(lines)+1}. 【{group_name}】{opt_name}")
                if opt_desc:
                    lines.append(f"   {opt_desc}")
        return "\n".join(lines) if lines else "无附加选项"

    def _format_account_list(self, accounts: List[Dict]) -> str:
        """格式化账户列表"""
        lines = []
        for i, acc in enumerate(accounts):
            acc_name = acc.get("accountName", "未知")
            acc_type = acc.get("payMethodText", "") or acc.get("payTypeText", "")
            lines.append(f"{i+1}. {acc_name} - {acc_type}")
        return "\n".join(lines) if lines else "系统默认账户"

    def _format_number_list(self, numbers: List[Dict]) -> str:
        """格式化号码列表"""
        lines = []
        for i, num in enumerate(numbers[:15]):
            code = num.get("code", "未知")
            lines.append(f"{i+1}. {code}")
        return "\n".join(lines) if lines else "无可用号码"

    def _format_iccid_list(self, iccids: List[Dict]) -> str:
        """格式化ICCID列表"""
        lines = []
        for i, res in enumerate(iccids[:10]):
            sim_info = res.get("simInfo", {})
            iccid = sim_info.get("iccid", "未知")
            card_type = sim_info.get("cardType", "")
            lines.append(f"{i+1}. {iccid} - {card_type}")
        return "\n".join(lines) if lines else "无可用ICCID"

    def _format_member_list(self, members: List[Dict]) -> str:
        """格式化成员列表"""
        lines = []
        for i, member in enumerate(members):
            prod_name = member.get("prodOfferName", "未知")
            access_types = []
            for access in member.get("accessTypeList", []):
                access_type = access.get("accessType", "未知")
                access_types.append(access_type)
            access_str = "、".join(access_types) if access_types else "未知"
            lines.append(f"{i+1}. {prod_name}（需要：{access_str}）")
        return "\n".join(lines) if lines else "无成员信息"

    def _format_offer_list(self, offers: List[Dict]) -> str:
        """格式化主销售品列表"""
        lines = []
        for i, offer in enumerate(offers):
            offer_name = offer.get("prodOfferName", "未知")
            offer_desc = offer.get("offerDescription", "")
            offer_fee = offer.get("offerFeeDescription", "")
            brand = offer.get("brandName", "")
            lines.append(f"{i+1}. {offer_name}")
            if brand:
                lines.append(f"   品牌：{brand}")
            if offer_fee:
                lines.append(f"   费用：{offer_fee}")
            if offer_desc:
                lines.append(f"   {offer_desc}")
        return "\n".join(lines) if lines else "暂无可订购套餐"