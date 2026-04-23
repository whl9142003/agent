"""
FastAPI Routes
CRM营业受理智能体API接口
"""
import uuid
import sys
import json
import os
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

# 会话存储路径
SESSION_DIR = BASE_DIR / "data" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session_to_file(session_id: str, messages: list, title: str = "", state_data: dict = None):
    """保存会话到文件"""
    filepath = SESSION_DIR / f"{session_id}.json"
    data = {
        "session_id": session_id,
        "title": title,
        "messages": messages,
        "state": state_data,
        "updated_at": datetime.now().isoformat()
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session_from_file(session_id: str) -> dict:
    """从文件加载会话"""
    filepath = SESSION_DIR / f"{session_id}.json"
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def delete_session_file(session_id: str):
    """删除会话文件"""
    filepath = SESSION_DIR / f"{session_id}.json"
    if filepath.exists():
        filepath.unlink()


def get_all_sessions_from_files() -> list:
    """从文件获取所有会话"""
    sessions = []
    for filepath in SESSION_DIR.glob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", filepath.stem),
                    "title": data.get("title", "新对话"),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": len(data.get("messages", []))
                })
        except:
            continue
    # 按更新时间倒序排列
    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return sessions

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
    language: Optional[str] = "zh"

class SessionRequest(BaseModel):
    session_id: str = ""

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
        _llm_service = create_llm()  # 使用 config.DEFAULT_PROVIDER，默认是 deepseek
        _agent = CRMAgent(_api_client, _llm_service)
        print(f"[Routes] Using LLM provider: {config.DEFAULT_PROVIDER}")

    return _agent


# ============ 会话管理接口 ============

@router.post("/session/create", response_model=SessionResponse)
async def create_session():
    """创建新会话"""
    session_id = str(uuid.uuid4())
    save_session_to_file(session_id, [], "新对话")
    return {
        "success": True,
        "session_id": session_id,
        "message": "会话创建成功"
    }


@router.get("/session/list")
async def list_sessions():
    """获取会话列表"""
    sessions = get_all_sessions_from_files()
    return {"success": True, "sessions": sessions}


@router.post("/session/load")
async def load_session(request: SessionRequest):
    """加载会话历史"""
    session_id = request.session_id
    if not session_id:
        return {"success": True, "session_id": "", "messages": []}

    data = load_session_from_file(session_id)
    if data:
        agent = get_agent()
        state = agent.get_session(session_id)
        state.set_conversation_history(data.get("messages", []))

        # 如果会话文件中有保存的状态信息且服务端会话状态有效，则恢复
        if data.get("state"):
            saved_auth = data.get("state", {}).get("authenticated", False)
            saved_customer_id = data.get("state", {}).get("customer_id")

            # 如果保存的状态是已认证且有客户ID，则恢复认证状态
            if saved_auth and saved_customer_id:
                state.from_dict(data.get("state"))
                print(f"[Session Load] Restored auth state: authenticated={state.authenticated}, customer_id={state.customer_id}")
                return {
                    "success": True,
                    "session_id": session_id,
                    "messages": data.get("messages", []),
                    "authenticated": True,
                    "customer_name": state.customer_name,
                    "customer_id": state.customer_id
                }

        # 未认证或状态无效，返回未认证状态
        print(f"[Session Load] No auth state in file")
        return {
            "success": True,
            "session_id": session_id,
            "messages": data.get("messages", []),
            "authenticated": False
        }
    return {
        "success": True,
        "session_id": session_id,
        "messages": []
    }


@router.post("/session/save")
async def save_session(request: SessionRequest):
    """保存会话"""
    session_id = request.session_id
    if not session_id:
        return {"success": True, "message": "会话ID为空"}
    
    agent = get_agent()
    state = agent.get_session(session_id)
    if state.conversation_history:
        title = ""
        for msg in state.conversation_history:
            if msg.get("role") == "user":
                title = msg.get("content", "")[:30]
                break
        state_data = state.to_dict()
        save_session_to_file(session_id, state.conversation_history, title, state_data)
    return {"success": True, "message": "会话已保存"}


@router.post("/session/clear")
async def clear_session(request: SessionRequest):
    """清除会话"""
    if request.session_id:
        agent = get_agent()
        agent.clear_session(request.session_id)
    return {"success": True, "message": "会话已清除"}


@router.post("/session/delete")
async def delete_session(request: SessionRequest):
    """删除会话"""
    if request.session_id:
        agent = get_agent()
        agent.clear_session(request.session_id)
        delete_session_file(request.session_id)
    return {"success": True, "message": "会话已删除"}


# ============ 对话接口 ============

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理对话消息"""
    agent = get_agent()

    try:
        response = await agent.process_message(
            session_id=request.session_id,
            message=request.message,
            language=request.language
        )
        
        # 保存会话到文件
        state = agent.get_session(request.session_id)
        if state.conversation_history:
            title = ""
            for msg in state.conversation_history:
                if msg.get("role") == "user":
                    title = msg.get("content", "")[:30]
                    break
            state_data = state.to_dict()
            save_session_to_file(request.session_id, state.conversation_history, title, state_data)

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
