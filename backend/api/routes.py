"""
FastAPI Routes
CRM营业受理智能体API接口
"""
import uuid
import sys
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from services.crm_agent import CRMAgent, CRMAPIClient
from services.llm_factory import create_llm, LLMFactory, BaseLLM
from typing import TYPE_CHECKING

# 请求模型
class AuthRequest(BaseModel):
    phone: str
    code: Optional[str] = None
    password: Optional[str] = None
    auth_type: str = "sms"

class SendCodeRequest(BaseModel):
    phone: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class CreateOrderRequest(BaseModel):
    session_id: str
    product_id: str

class PaymentRequest(BaseModel):
    session_id: str
    order_id: str
    payment_method: str = "account_balance"

# 响应模型
class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    customer: Optional[dict] = None

class ChatResponse(BaseModel):
    success: bool
    message: str
    type: str
    data: Optional[dict] = None

class SessionResponse(BaseModel):
    success: bool
    session_id: str
    message: str

# 创建路由器
router = APIRouter()

# 全局实例
_llm_service: Optional[BaseLLM] = None
_api_client: Optional[CRMAPIClient] = None
_agent: Optional[CRMAgent] = None


def get_agent() -> CRMAgent:
    """获取Agent实例"""
    global _llm_service, _api_client, _agent

    if _agent is None:
        _api_client = CRMAPIClient(base_url=config.CRM_API_BASE_URL)
        _llm_service = create_llm()
        _agent = CRMAgent(_api_client, _llm_service)

    return _agent


# ============ 会话管理接口 ============

@router.post("/session/create", response_model=SessionResponse)
async def create_session():
    """创建新会话"""
    session_id = str(uuid.uuid4())
    return {
        "success": True,
        "session_id": session_id,
        "message": "会话创建成功"
    }


@router.post("/session/clear")
async def clear_session(session_id: str):
    """清除会话"""
    agent = get_agent()
    agent.clear_session(session_id)
    return {"success": True, "message": "会话已清除"}


# ============ 认证接口 ============

@router.post("/auth/send-code")
async def send_verification_code(request: SendCodeRequest):
    """发送验证码"""
    agent = get_agent()
    result = await agent.api_client.send_verification_code(request.phone)
    return result


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    """登录认证"""
    agent = get_agent()
    result = await agent.api_client.authenticate(
        phone=request.phone,
        code=request.code,
        password=request.password,
        auth_type=request.auth_type
    )

    if result.get("success"):
        # 创建会话
        session_id = str(uuid.uuid4())
        state = agent.get_session(session_id)

        # 设置用户信息
        customer = result.get("customer", {})
        state.authenticated = True
        state.customer_id = customer.get("customer_id")
        state.customer_name = customer.get("name")
        state.phone = customer.get("phone")
        state.account_balance = customer.get("account_balance", 0)
        state.current_package = customer.get("current_package", "")

        return {
            "success": True,
            "message": "登录成功",
            "token": session_id,
            "customer": customer
        }

    return {
        "success": False,
        "message": result.get("detail", "认证失败"),
        "token": None,
        "customer": None
    }


# ============ 对话接口 ============

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理对话消息"""
    agent = get_agent()

    try:
        response = await agent.process_message(
            session_id=request.session_id,
            message=request.message
        )

        return {
            "success": True,
            "message": response.get("message", ""),
            "type": response.get("type", "text"),
            "data": {
                k: v for k, v in response.items()
                if k not in ["message", "type"]
            }
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"处理消息时发生错误：{str(e)}",
            "type": "error"
        }


# ============ 产品接口 ============

@router.get("/products")
async def get_products(keyword: Optional[str] = None):
    """获取产品列表"""
    agent = get_agent()
    result = await agent.api_client.get_products(keyword=keyword)
    return result


@router.get("/products/{product_id}")
async def get_product_detail(product_id: str):
    """获取产品详情"""
    agent = get_agent()
    result = await agent.api_client.get_product_detail(product_id)
    return result


@router.get("/products/recommend/{customer_id}")
async def get_recommendations(customer_id: str):
    """获取产品推荐"""
    agent = get_agent()
    result = await agent.api_client.get_recommendations(customer_id)
    return result


# ============ 订单接口 ============

@router.post("/orders")
async def create_order(session_id: str, product_id: str, product_name: str, price: float):
    """创建订单"""
    agent = get_agent()
    state = agent.get_session(session_id)

    if not state.authenticated:
        raise HTTPException(status_code=401, detail="请先完成身份认证")

    result = await agent.api_client.create_order(
        customer_id=state.customer_id,
        product_id=product_id,
        product_name=product_name,
        price=price
    )
    return result


@router.get("/orders/{customer_id}")
async def get_orders(customer_id: str):
    """获取订单列表"""
    agent = get_agent()
    result = await agent.api_client.get_orders(customer_id)
    return result


@router.get("/orders/detail/{order_id}")
async def get_order_detail(order_id: str):
    """获取订单详情"""
    agent = get_agent()
    result = await agent.api_client.get_order_detail(order_id)
    return result


# ============ 支付接口 ============

@router.post("/payment")
async def process_payment(session_id: str, order_id: str, payment_method: str = "account_balance"):
    """处理支付"""
    agent = get_agent()
    state = agent.get_session(session_id)

    if not state.authenticated:
        raise HTTPException(status_code=401, detail="请先完成身份认证")

    result = await agent.api_client.process_payment(
        order_id=order_id,
        customer_id=state.customer_id,
        payment_method=payment_method
    )
    return result


# ============ 客户信息接口 ============

class CustomerQueryRequest(BaseModel):
    phone: str

class OffersQueryRequest(BaseModel):
    cust_id: str

class SubOffersQueryRequest(BaseModel):
    offer_inst_id: str


@router.post("/customer/query")
async def query_customer(request: CustomerQueryRequest):
    """客户查询 /CCInter/open/cust/query"""
    agent = get_agent()
    result = await agent.api_client.query_customer(request.phone)
    return result


@router.post("/customer/offers")
async def query_customer_offers(request: OffersQueryRequest):
    """客户订购产品查询 /CCInter/open/cust/offers"""
    agent = get_agent()
    result = await agent.api_client.query_customer_offers(request.cust_id)
    return result


@router.post("/customer/offers/sub")
async def query_sub_offers(request: SubOffersQueryRequest):
    """附属销售品查询 /CCInter/open/cust/sub/offers"""
    agent = get_agent()
    result = await agent.api_client.query_sub_offers(request.offer_inst_id)
    return result


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """获取会话状态"""
    agent = get_agent()
    state = agent.get_session(session_id)

    return {
        "success": True,
        "authenticated": state.authenticated,
        "customer_id": state.customer_id,
        "customer_name": state.customer_name,
        "current_package": state.current_package,
        "account_balance": state.account_balance
    }
