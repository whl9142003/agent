"""
Mock CRM API Server
模拟CRM系统RESTful接口服务
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime

app = FastAPI(title="Mock CRM API")

# ============ 数据模型 ============

class AuthRequest(BaseModel):
    phone: str
    code: Optional[str] = None
    password: Optional[str] = None
    auth_type: str  # "sms" or "password"

class SendCodeRequest(BaseModel):
    phone: str

class ProductQuery(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None

class OrderCreateRequest(BaseModel):
    customer_id: str
    product_id: str
    product_name: str
    price: float

class PaymentRequest(BaseModel):
    order_id: str
    payment_method: str  # "account_balance"
    customer_id: str

# ============ 模拟数据 ============

# 客户数据
MOCK_CUSTOMERS = {
    "13800000000": {
        "customer_id": "C001",
        "phone": "13800000000",
        "name": "张**",
        "full_name": "张三",
        "id_card": "310***********1234",
        "account_id": "A001",
        "account_balance": 256.00,
        "subscriber_id": "S001",
        "current_package": "5G畅享套餐",
        "package_price": 128
    },
    "13900000000": {
        "customer_id": "C002",
        "phone": "13900000000",
        "name": "李**",
        "full_name": "李四",
        "id_card": "320***********5678",
        "account_id": "A002",
        "account_balance": 500.00,
        "subscriber_id": "S002",
        "current_package": "4G自由套餐",
        "package_price": 88
    }
}

# 产品数据
MOCK_PRODUCTS = [
    {
        "product_id": "P001",
        "name": "5G畅享套餐",
        "category": "5G套餐",
        "price": 128,
        "data_quota": "30GB",
        "voice_quota": "500分钟",
        "description": "适合日常使用，性价比高",
        "applicable": True
    },
    {
        "product_id": "P002",
        "name": "5G尊享套餐",
        "category": "5G套餐",
        "price": 198,
        "data_quota": "50GB",
        "voice_quota": "1000分钟",
        "description": "重度用户，流量充足",
        "applicable": True
    },
    {
        "product_id": "P003",
        "name": "5G轻享套餐",
        "category": "5G套餐",
        "price": 68,
        "data_quota": "10GB",
        "voice_quota": "200分钟",
        "description": "轻度用户，经济实惠",
        "applicable": True
    },
    {
        "product_id": "P004",
        "name": "流量加油包（10GB）",
        "category": "增值包",
        "price": 30,
        "data_quota": "10GB",
        "voice_quota": "0分钟",
        "description": "流量补充包，当月有效",
        "applicable": True
    },
    {
        "product_id": "P005",
        "name": "国际漫游包",
        "category": "增值包",
        "price": 98,
        "data_quota": "5GB",
        "voice_quota": "100分钟",
        "description": "出国漫游专用",
        "applicable": False,
        "reason": "仅对高价值客户开放"
    }
]

# 订单数据
MOCK_ORDERS = {}

# ============ 认证接口 ============

CRM_API_URL = "https://192.168.2.84:8081"
VERIFY_CODE_URL = f"{CRM_API_URL}/ecare-boot/user/login"

async def call_crm_login(phone: str, password: str, serial_number: str = None) -> dict:
    """调用真实CRM登录接口"""
    import httpx

    serial_num = serial_number or f"{int(datetime.now().timestamp() * 1000)}"

    payload = {
        "language": "en_US",
        "ticketId": "",
        "serialNumber": serial_num,
        "parameterObj": {
            "account": phone,
            "password": password,
            "captchaCode": "",
            "captchaId": "",
            "notRobotFlag": True,
            "reserv3": "1"
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
    }

    try:
        print(f"[CRM Login] Calling CRM API for phone: {phone}")
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(
                VERIFY_CODE_URL,
                json=payload,
                headers=headers
            )
            result = response.json()
            print(f"[CRM Login] Response: {result}")

            if result.get("code") == "0":
                user_data = result.get("resultObj", {})
                customer = {
                    "customer_id": user_data.get("operUserId", ""),
                    "phone": phone,
                    "name": user_data.get("userName", ""),
                    "full_name": user_data.get("userName", ""),
                    "account_id": user_data.get("operUserId", ""),
                    "account_balance": 0.0,  # 需要另外查询
                    "subscriber_id": user_data.get("operUserId", ""),
                    "current_package": "未知套餐",
                    "package_price": 0,
                    "ticket_id": user_data.get("ticketId", ""),
                    "role_id": user_data.get("roleId", ""),
                    "user_type": user_data.get("userType", ""),
                    "cust_type": user_data.get("custType", "")
                }
                return {"success": True, "customer": customer}
            else:
                error_msg = result.get("detail") or result.get("message") or "登录失败"
                return {"success": False, "message": error_msg}
    except httpx.ConnectError as e:
        print(f"[CRM Login] Connection error: {e}")
        return {"success": False, "message": f"无法连接到CRM系统: {str(e)}"}
    except Exception as e:
        print(f"[CRM Login] Error: {e}")
        return {"success": False, "message": f"调用CRM接口失败: {str(e)}"}


@app.post("/api/auth/send-code")
async def send_verification_code(request: SendCodeRequest):
    """发送验证码"""
    return {
        "success": True,
        "message": "验证码已发送",
        "code": "123456"
    }


@app.post("/api/auth/login")
async def login(request: AuthRequest):
    """身份认证 - 调用真实CRM接口"""
    # 调用真实CRM登录接口
    result = await call_crm_login(
        phone=request.phone,
        password=request.password or "Tianyuan@410"
    )

    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("message", "登录失败"))

    customer = result.get("customer", {})
    session_token = str(uuid.uuid4())

    # 保存客户信息到本地
    MOCK_CUSTOMERS[request.phone] = customer

    return {
        "success": True,
        "message": "认证成功",
        "token": session_token,
        "customer": {
            "customer_id": customer["customer_id"],
            "phone": customer["phone"],
            "name": customer["name"],
            "full_name": customer["full_name"],
            "account_id": customer["account_id"],
            "account_balance": customer["account_balance"],
            "subscriber_id": customer["subscriber_id"],
            "current_package": customer["current_package"],
            "package_price": customer["package_price"],
            "ticket_id": customer.get("ticket_id", "")
        }
    }

    phone = request.phone
    if phone not in MOCK_CUSTOMERS:
        # 模拟新用户注册
        new_customer = {
            "customer_id": f"C{len(MOCK_CUSTOMERS) + 1:03d}",
            "phone": phone,
            "name": phone[:3] + "**",
            "full_name": f"用户{phone[-4:]}",
            "id_card": f"000***********{phone[-4:]}",
            "account_id": f"A{len(MOCK_CUSTOMERS) + 1:03d}",
            "account_balance": 100.00,
            "subscriber_id": f"S{len(MOCK_CUSTOMERS) + 1:03d}",
            "current_package": "新用户套餐",
            "package_price": 58
        }
        MOCK_CUSTOMERS[phone] = new_customer

    customer = MOCK_CUSTOMERS[phone]
    session_token = str(uuid.uuid4())

    return {
        "success": True,
        "message": "认证成功",
        "token": session_token,
        "customer": {
            "customer_id": customer["customer_id"],
            "phone": customer["phone"],
            "name": customer["name"],
            "full_name": customer["full_name"],
            "account_id": customer["account_id"],
            "account_balance": customer["account_balance"],
            "subscriber_id": customer["subscriber_id"],
            "current_package": customer["current_package"],
            "package_price": customer["package_price"]
        }
    }

# ============ 产品接口 ============

@app.get("/api/products")
async def get_products(keyword: Optional[str] = None, category: Optional[str] = None):
    """获取产品列表"""
    products = MOCK_PRODUCTS.copy()

    if keyword:
        products = [p for p in products if keyword.lower() in p["name"].lower()]
    if category:
        products = [p for p in products if p["category"] == category]

    return {
        "success": True,
        "products": products,
        "total": len(products)
    }

@app.get("/api/products/{product_id}")
async def get_product_detail(product_id: str):
    """获取产品详情"""
    for product in MOCK_PRODUCTS:
        if product["product_id"] == product_id:
            return {
                "success": True,
                "product": product
            }
    raise HTTPException(status_code=404, detail="产品不存在")

# ============ 产品推荐 ============

@app.get("/api/products/recommend/{customer_id}")
async def get_product_recommend(customer_id: str):
    """获取个性化推荐"""
    # 模拟基于客户信息的推荐
    customer = None
    for c in MOCK_CUSTOMERS.values():
        if c["customer_id"] == customer_id:
            customer = c
            break

    if not customer:
        return {
            "success": True,
            "recommendations": MOCK_PRODUCTS[:3]
        }

    # 根据客户当前套餐推荐
    recommendations = []
    for product in MOCK_PRODUCTS:
        if product["applicable"]:
            recommendations.append(product)
            if len(recommendations) >= 3:
                break

    return {
        "success": True,
        "recommendations": recommendations,
        "customer_usage": {
            "avg_data": "约25GB/月",
            "avg_voice": "约400分钟/月"
        }
    }

# ============ 订单接口 ============

@app.post("/api/orders")
async def create_order(request: OrderCreateRequest):
    """创建订单"""
    order_id = f"ORD{datetime.now().strftime('%Y%m%d')}{len(MOCK_ORDERS) + 1:04d}"

    order = {
        "order_id": order_id,
        "customer_id": request.customer_id,
        "product_id": request.product_id,
        "product_name": request.product_name,
        "price": request.price,
        "status": "pending_payment",
        "create_time": datetime.now().isoformat(),
        "payment_time": None,
        "complete_time": None
    }

    MOCK_ORDERS[order_id] = order

    return {
        "success": True,
        "message": "订单创建成功",
        "order": order
    }

@app.get("/api/orders/{customer_id}")
async def get_customer_orders(customer_id: str):
    """获取客户订单列表"""
    orders = [o for o in MOCK_ORDERS.values() if o["customer_id"] == customer_id]

    return {
        "success": True,
        "orders": orders,
        "total": len(orders)
    }

@app.get("/api/orders/detail/{order_id}")
async def get_order_detail(order_id: str):
    """获取订单详情"""
    if order_id not in MOCK_ORDERS:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = MOCK_ORDERS[order_id]

    # 模拟订单进度
    progress = []
    if order["status"] == "pending_payment":
        progress = [
            {"step": "订单提交", "status": "completed", "time": order["create_time"]},
            {"step": "订单审核", "status": "pending", "time": None},
            {"step": "处理中", "status": "pending", "time": None},
            {"step": "已完成", "status": "pending", "time": None}
        ]
    elif order["status"] == "paid":
        progress = [
            {"step": "订单提交", "status": "completed", "time": order["create_time"]},
            {"step": "订单审核", "status": "completed", "time": order["payment_time"]},
            {"step": "处理中", "status": "completed", "time": order["payment_time"]},
            {"step": "已完成", "status": "pending", "time": None}
        ]
    elif order["status"] == "completed":
        progress = [
            {"step": "订单提交", "status": "completed", "time": order["create_time"]},
            {"step": "订单审核", "status": "completed", "time": order["payment_time"]},
            {"step": "处理中", "status": "completed", "time": order["complete_time"]},
            {"step": "已完成", "status": "completed", "time": order["complete_time"]}
        ]

    return {
        "success": True,
        "order": order,
        "progress": progress
    }

# ============ 支付接口 ============

@app.post("/api/payment/pay")
async def process_payment(request: PaymentRequest):
    """处理支付"""
    if request.order_id not in MOCK_ORDERS:
        raise HTTPException(status_code=404, detail="订单不存在")

    order = MOCK_ORDERS[request.order_id]

    # 获取客户账户信息
    customer = None
    for c in MOCK_CUSTOMERS.values():
        if c["customer_id"] == request.customer_id:
            customer = c
            break

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 检查余额
    if customer["account_balance"] < order["price"]:
        return {
            "success": False,
            "message": "余额不足",
            "required": order["price"],
            "available": customer["account_balance"]
        }

    # 执行扣款
    MOCK_CUSTOMERS[customer["phone"]]["account_balance"] -= order["price"]

    # 更新订单状态
    order["status"] = "paid"
    order["payment_time"] = datetime.now().isoformat()

    return {
        "success": True,
        "message": "支付成功",
        "order": order,
        "payment": {
            "payment_method": request.payment_method,
            "amount": order["price"],
            "payment_time": order["payment_time"],
            "remaining_balance": MOCK_CUSTOMERS[customer["phone"]]["account_balance"]
        }
    }

# ============ 客户信息接口 ============

@app.get("/api/customer/{customer_id}")
async def get_customer_info(customer_id: str):
    """获取客户三户信息"""
    for customer in MOCK_CUSTOMERS.values():
        if customer["customer_id"] == customer_id:
            return {
                "success": True,
                "customer": customer
            }
    raise HTTPException(status_code=404, detail="客户不存在")

# ============ 账户余额查询 ============

@app.get("/api/account/balance/{customer_id}")
async def get_account_balance(customer_id: str):
    """获取账户余额"""
    for customer in MOCK_CUSTOMERS.values():
        if customer["customer_id"] == customer_id:
            return {
                "success": True,
                "account_id": customer["account_id"],
                "balance": customer["account_balance"]
            }
    raise HTTPException(status_code=404, detail="客户不存在")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
