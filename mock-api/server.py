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
    },
    "15300000574": {
        "customer_id": "120000",
        "phone": "15300000574",
        "name": "mola81",
        "full_name": "mola81",
        "id_card": "320***********5678",
        "account_id": "A003",
        "account_balance": 128.00,
        "subscriber_id": "S003",
        "current_package": "5G套餐",
        "package_price": 128
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
MOCK_ORDERS = {
    "ORD20260423001": {
        "order_id": "ORD20260423001",
        "customer_id": "120000",
        "product_name": "5G Smart Offer",
        "status": "已完成",
        "create_time": "2026-04-23 10:30:00",
        "amount": 99.00
    },
    "ORD20260422002": {
        "order_id": "ORD20260422002",
        "customer_id": "120000",
        "product_name": "CUG GROUP Offer",
        "status": "已完成",
        "create_time": "2026-04-22 14:20:00",
        "amount": 50.00
    },
    "ORD20260421003": {
        "order_id": "ORD20260421003",
        "customer_id": "120000",
        "product_name": "云主机服务器套餐",
        "status": "处理中",
        "create_time": "2026-04-21 09:15:00",
        "amount": 200.00
    }
}

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
        print(f"[CRM Login] Step 1: Calling CRM API: {VERIFY_CODE_URL}")
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            # Step 1: 调用登录接口
            response = await client.post(
                VERIFY_CODE_URL,
                json=payload,
                headers=headers
            )
            result = response.json()
            print(f"[CRM Login] Step 1 Response: {result}")

            if result.get("code") != "0":
                error_msg = result.get("detail") or result.get("message") or "登录失败"
                return {"success": False, "message": error_msg}
            
            user_data = result.get("resultObj", {})
            cust_id = user_data.get("operUserId", "")
            
            # Step 2: 调用 /CCInter/open/cust/query 获取客户信息
            print(f"[CRM Login] Step 2: Calling /CCInter/open/cust/query")
            cust_response = await client.post(
                f"{CRM_API_URL}/CCInter/open/cust/query",
                json={"custVal": phone},
                headers=headers
            )
            cust_result = cust_response.json()
            print(f"[CRM Login] Step 2 Response: {cust_result}")
            
            if cust_result.get("code") == "0" and cust_result.get("resultObj", {}).get("list"):
                cust_data = cust_result["resultObj"]["list"][0]
                cust_id = cust_data.get("custId", "") or cust_id
                cust_name = cust_data.get("custName", "")
            else:
                cust_name = user_data.get("userName", "")
            
            current_package = "未知套餐"
            account_balance = 0.0
            offers_list = []
            
            # Step 3: 调用 /CCInter/open/cust/offers 获取已订购产品
            if cust_id:
                print(f"[CRM Login] Step 3: Calling /CCInter/open/cust/offers")
                try:
                    offers_response = await client.post(
                        f"{CRM_API_URL}/CCInter/open/cust/offers",
                        json={"custId": cust_id},
                        headers=headers
                    )
                    offers_result = offers_response.json()
                    print(f"[CRM Login] Step 3 Response: {offers_result}")
                    
                    if offers_result.get("code") == "0":
                        offers_list = offers_result.get("resultObj", {}).get("list", [])
                        if offers_list:
                            current_package = offers_list[0].get("offerName", "未知套餐")
                            
                            # 如果CRM返回的subOfferInst为空，则调用Step 4获取
                            for offer in offers_list:
                                existing_sub = offer.get("subOfferInst", [])
                                if not existing_sub:
                                    offer_inst_id = offer.get("offerInstId", "")
                                    if offer_inst_id:
                                        print(f"[CRM Login] Step 4: Calling /CCInter/open/cust/sub/offers")
                                        try:
                                            sub_response = await client.post(
                                                f"{CRM_API_URL}/CCInter/open/cust/sub/offers",
                                                json={"offerInstId": offer_inst_id},
                                                headers=headers
                                            )
                                            sub_result = sub_response.json()
                                            print(f"[CRM Login] Step 4 Response: {sub_result}")
                                            
                                            if sub_result.get("code") == "0":
                                                offer["subOfferInst"] = sub_result.get("resultObj", {}).get("list", [])
                                            else:
                                                offer["subOfferInst"] = []
                                        except Exception as e:
                                            print(f"[CRM Login] Step 4 Error: {e}")
                                            offer["subOfferInst"] = []
                except Exception as e:
                    print(f"[CRM Login] Step 3 Error: {e}")
            
            customer = {
                "customer_id": cust_id,
                "phone": phone,
                "name": cust_name,
                "full_name": cust_name,
                "account_id": cust_id,
                "account_balance": account_balance,
                "subscriber_id": cust_id,
                "current_package": current_package,
                "package_price": 0,
                "ticket_id": user_data.get("ticketId", ""),
                "role_id": user_data.get("roleId", ""),
                "user_type": user_data.get("userType", ""),
                "cust_type": user_data.get("custType", ""),
                "offers": offers_list
            }
            print(f"[CRM Login] Final customer: {customer}")
            return {"success": True, "customer": customer}
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
    """身份认证 - 使用fallback机制"""
    # 先尝试调用真实CRM登录接口，如果失败则使用fallback
    try:
        result = await call_crm_login(
            phone=request.phone,
            password=request.password or "Tianyuan@410"
        )
    except Exception as e:
        print(f"[Login] CRM API failed, using fallback: {e}")
        result = {"success": False, "message": str(e)}

    # 如果真实API失败，使用fallback客户数据
    if not result.get("success"):
        # Fallback: 接受任意6位以上密码，创建模拟客户
        if request.password and len(request.password) >= 6:
            phone = request.phone
            # 使用已存在的客户或创建新的
            if phone in MOCK_CUSTOMERS:
                customer = MOCK_CUSTOMERS[phone]
            else:
                customer = {
                    "customer_id": f"C{len(MOCK_CUSTOMERS) + 1:03d}",
                    "phone": phone,
                    "name": f"用户{phone[-4:]}",
                    "full_name": f"测试用户{phone[-4:]}",
                    "account_id": f"A{len(MOCK_CUSTOMERS) + 1:03d}",
                    "account_balance": 100.00,
                    "subscriber_id": f"S{len(MOCK_CUSTOMERS) + 1:03d}",
                    "current_package": "5G畅享套餐128",
                    "package_price": 128,
                    "ticket_id": f"T{len(MOCK_CUSTOMERS) + 1:03d}",
                    "offers": [
                        {
                            "prodOfferId": 700000053,
                            "prodOfferName": "5G畅享套餐128",
                            "offerNbr": "600000053",
                            "offerDescription": "5G畅享套餐128元档",
                            "offerFeeDescription": "128元/月",
                            "state": "003",
                            "effDate": "2024-01-01 00:00:00",
                            "expDate": "2034-01-01 00:00:00",
                            "brandId": "1",
                            "brandName": "全球通"
                        }
                    ]
                }
                MOCK_CUSTOMERS[phone] = customer

            session_token = str(uuid.uuid4())
            return {
                "success": True,
                "message": "认证成功",
                "token": session_token,
                "customer": customer
            }
        else:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

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
            "ticket_id": customer.get("ticket_id", ""),
            "offers": customer.get("offers", [])
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
async def get_products(keyword: Optional[str] = None, category: Optional[str] = None, custId: Optional[str] = None):
    """获取产品列表 - 调用真实CRM接口"""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            headers = {
                "Content-Type": "application/json",
                "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
            }
            
            cust_id = custId or "120000"
            response = await client.post(
                f"{CRM_API_URL}/CCInter/open/order/offers",
                json={"custId": cust_id},
                headers=headers
            )
            result = response.json()
            
            if result.get("code") == "0":
                offer_list = result.get("resultObj", {}).get("list", [])
                products = []
                for offer in offer_list:
                    name = offer.get("prodOfferName", "未知")
                    if keyword and keyword.lower() not in name.lower():
                        continue
                    products.append({
                        "product_id": str(offer.get("prodOfferId", "")),
                        "name": name,
                        "price": offer.get("offerFeeDescription", "标准资费"),
                        "description": offer.get("offerDescription", ""),
                        "category": category or "offer",
                        "eff_date": offer.get("effDate", ""),
                        "exp_date": offer.get("expDate", "")
                    })
                
                return {
                    "success": True,
                    "products": products,
                    "total": len(products)
                }
            else:
                return {
                    "success": True,
                    "products": [],
                    "message": result.get("message", "查询失败")
                }
    except Exception as e:
        print(f"[Mock] get_products error: {e}")
        return {
            "success": True,
            "products": [],
            "message": str(e)
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
    """获取个性化推荐 - 调用真实CRM接口"""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            headers = {
                "Content-Type": "application/json",
                "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
            }
            
            response = await client.post(
                f"{CRM_API_URL}/CCInter/open/order/offers",
                json={"custId": customer_id},
                headers=headers
            )
            result = response.json()
            
            if result.get("code") == "0":
                offer_list = result.get("resultObj", {}).get("list", [])
                recommendations = []
                for offer in offer_list:
                    recommendations.append({
                        "product_id": str(offer.get("prodOfferId", "")),
                        "name": offer.get("prodOfferName", "未知"),
                        "price": offer.get("offerFeeDescription", "标准资费"),
                        "description": offer.get("offerDescription", ""),
                        "category": "offer"
                    })
                
                return {
                    "success": True,
                    "recommendations": recommendations[:6],
                    "customer_usage": {
                        "avg_data": "约25GB/月",
                        "avg_voice": "约400分钟/月"
                    }
                }
            else:
                return {
                    "success": True,
                    "recommendations": [],
                    "message": result.get("message", "查询失败")
                }
    except Exception as e:
        print(f"[Mock] get_product_recommend error: {e}")
        return {
            "success": True,
            "recommendations": [],
            "message": str(e)
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

# ============ 客户信息查询 ============

@app.post("/CCInter/open/cust/query")
async def query_customer(request: dict):
    """CRM客户信息查询接口"""
    cust_val = request.get("custVal", "")
    print(f"[Mock] query_customer called with custVal: {cust_val}")
    
    # 查找匹配的客户
    for phone, customer in MOCK_CUSTOMERS.items():
        if phone == cust_val or customer.get("customer_id") == cust_val:
            print(f"[Mock] Found customer: {customer}")
            return {
                "code": "0",
                "message": "成功",
                "resultObj": {
                    "list": [{
                        "custId": customer["customer_id"],
                        "custName": customer["name"],
                        "custType": customer.get("cust_type", "个人"),
                        "phone": customer["phone"],
                        "acctId": customer["account_id"],
                        "subscriberId": customer["subscriber_id"]
                    }]
                }
            }
    
    # 新用户，返回模拟数据
    mock_cust_id = f"C{len(MOCK_CUSTOMERS) + 1:03d}"
    mock_customer = {
        "custId": mock_cust_id,
        "custName": f"用户{cust_val[-4:]}",
        "custType": "个人",
        "phone": cust_val,
        "acctId": f"A{len(MOCK_CUSTOMERS) + 1:03d}",
        "subscriberId": f"S{len(MOCK_CUSTOMERS) + 1:03d}"
    }
    print(f"[Mock] Returning mock customer: {mock_customer}")
    
    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "list": [mock_customer]
        }
    }


@app.post("/CCInter/open/cust/offers")
async def query_customer_offers(request: dict):
    """客户订购主销售品查询"""
    cust_id = request.get("custId", "")
    print(f"[Mock] query_customer_offers called with custId: {cust_id}")

    # Customer 15300000574 -> cust_id = "120000"
    if cust_id == "120000":
        cust_id = "120000"
    else:
        cust_id = cust_id or "C001"

    # 模拟已订购产品数据
    if cust_id == "120000":
        mock_offers = [
            {
                "offerInstId": "O001-120000",
                "offerName": "5G畅享128套餐",
                "regionName": "上海市",
                "effDate": "2024-01-01T00:00:00",
                "expDate": "2099-12-31T23:59:59",
                "subscribeDate": "2024-01-01T10:30:00",
                "productOfferType": "6",
                "status": "1",
                "subOfferInst": [
                    {
                        "offerInstId": "SO001-120000",
                        "offerName": "来电显示",
                        "billingNo": "15300000574",
                        "contractCd": "CON20240101001",
                        "effDate": "2024-01-01T00:00:00",
                        "expDate": "2099-12-31T23:59:59",
                        "status": "1"
                    },
                    {
                        "offerInstId": "SO002-120000",
                        "offerName": "短信包",
                        "billingNo": "15300000574",
                        "contractCd": "CON20240101002",
                        "effDate": "2024-01-01T00:00:00",
                        "expDate": "2099-12-31T23:59:59",
                        "status": "1"
                    }
                ]
            },
            {
                "offerInstId": "O002-120000",
                "offerName": "流量加油包(10GB)",
                "regionName": "上海市",
                "effDate": "2026-04-01T00:00:00",
                "expDate": "2026-04-30T23:59:59",
                "subscribeDate": "2026-04-01T10:30:00",
                "productOfferType": "11",
                "status": "1",
                "subOfferInst": []
            }
        ]
    else:
        mock_offers = [
            {
                "offerInstId": f"O001-{cust_id}",
                "offerName": "5G畅享128套餐",
                "regionName": "上海市",
                "effDate": "2024-01-01T00:00:00",
                "expDate": "2099-12-31T23:59:59",
                "subscribeDate": "2024-01-01T10:30:00",
                "productOfferType": "6",
                "status": "1",
                "subOfferInst": [
                    {
                        "offerInstId": f"SO001-{cust_id}",
                        "offerName": "来电显示",
                        "billingNo": "13800000001",
                        "contractCd": "CON20240101001",
                        "effDate": "2024-01-01T00:00:00",
                        "expDate": "2099-12-31T23:59:59",
                        "status": "1"
                    },
                    {
                        "offerInstId": f"SO002-{cust_id}",
                        "offerName": "短信包",
                        "billingNo": "13800000002",
                        "contractCd": "CON20240101002",
                        "effDate": "2024-01-01T00:00:00",
                        "expDate": "2099-12-31T23:59:59",
                        "status": "1"
                    }
                ]
            },
            {
                "offerInstId": f"O002-{cust_id}",
                "offerName": "流量加油包(10GB)",
                "regionName": "上海市",
                "effDate": "2026-04-01T00:00:00",
                "expDate": "2026-04-30T23:59:59",
                "subscribeDate": "2026-04-01T10:30:00",
                "productOfferType": "11",
                "status": "1",
                "subOfferInst": []
            }
        ]
    
    print(f"[Mock] Returning offers: {len(mock_offers)} items")
    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "list": mock_offers
        }
    }


@app.post("/CCInter/open/cust/sub/offers")
async def query_sub_offers(request: dict):
    """客户订购附属销售品查询"""
    offer_inst_id = request.get("offerInstId", "")
    print(f"[Mock] query_sub_offers called with offerInstId: {offer_inst_id}")
    
    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "list": []
        }
    }


@app.post("/CCInter/open/order/offers")
async def query_order_offers(request: dict):
    """可订购销售品查询 - 调用真实CRM接口"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    cust_id = request.get("custId", "")
    keyword = request.get("prodOfferNameOrBrandName", "")
    print(f"[Mock] query_order_offers called with custId: {cust_id}, keyword: {keyword}")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
    }

    try:
        response = requests.post(
            f"{CRM_API_URL}/CCInter/open/order/offers",
            json={"custId": cust_id, "prodOfferNameOrBrandName": keyword} if keyword else {"custId": cust_id},
            headers=headers,
            verify=False,
            timeout=60
        )
        result = response.json()
        print(f"[Mock] CRM order offers response: code={result.get('code')}, count={len(result.get('resultObj', {}).get('list', []))}")
        return result
    except Exception as e:
        print(f"[Mock] CRM order offers error: {e}")
        return {"code": "-1", "message": str(e), "resultObj": None}


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


@app.post("/CCInter/open/offers/query")
async def query_offers(request: dict):
    """可订购销售品查询 - 调用真实CRM接口"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    keyword = request.get("prodOfferNameOrBrandName", "")
    print(f"[Mock] query_offers called with keyword: {keyword}")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
    }

    try:
        payload = {}
        if keyword:
            payload["prodOfferNameOrBrandName"] = keyword
        
        response = requests.post(
            f"{CRM_API_URL}/CCInter/open/offers/query",
            json=payload,
            headers=headers,
            verify=False,
            timeout=60
        )
        result = response.json()
        print(f"[Mock] CRM offers query response: code={result.get('code')}, count={len(result.get('resultObj', []))}")
        return result
    except Exception as e:
        print(f"[Mock] CRM offers query error: {e}")
        return {"code": "-1", "message": str(e), "resultObj": []}


@app.post("/CCInter/open/order/optgroup/offers")
async def query_optgroup_offers(request: dict):
    """获取附属销售品组 - 调用真实CRM接口"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    pkg_offer_id = request.get("pkgOfferId", "")
    print(f"[Mock] query_optgroup_offers called with pkgOfferId: {pkg_offer_id}")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
    }

    try:
        response = requests.post(
            f"{CRM_API_URL}/CCInter/open/order/optgroup/offers",
            json={"pkgOfferId": pkg_offer_id},
            headers=headers,
            verify=False,
            timeout=60
        )
        result = response.json()
        print(f"[Mock] CRM optgroup offers response: code={result.get('code')}, count={len(result.get('resultObj', []))}")
        return result
    except Exception as e:
        print(f"[Mock] CRM optgroup offers error: {e}")
        return {"code": "-1", "message": str(e), "resultObj": []}


# ============ 客户账户查询 ============
@app.post("/CCInter/open/cust/accounts")
async def query_customer_accounts(request: dict):
    """查询客户账户信息 - 调用真实CRM接口并分页获取"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    cust_id = request.get("custId", "")
    print(f"[Mock] query_customer_accounts called with custId: {cust_id}")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"{CRM_API_URL}/ecare/login.view?lang=zh_CN"
    }

    all_accounts = []
    page_num = 1
    page_size = 10

    try:
        while True:
            try:
                response = requests.post(
                    f"{CRM_API_URL}/CCInter/open/cust/accounts",
                    json={"custId": cust_id, "pageNum": page_num, "pageSize": page_size},
                    headers=headers,
                    verify=False,
                    timeout=60
                )
            except Exception as e:
                print(f"[Mock] Request error: {e}")
                return {"code": "-1", "message": f"请求CRM接口失败: {str(e)}", "resultObj": None}
            
            try:
                result = response.json()
            except Exception as e:
                print(f"[Mock] JSON parse error: {e}, response={response.text[:200] if response.text else 'empty'}")
                return {"code": "-1", "message": f"解析响应失败: {str(e)}", "resultObj": None}
            
            if result.get("code") != "0":
                print(f"[Mock] CRM accounts error: {result}")
                return result
            
            result_obj = result.get("resultObj", {})
            page_info = result_obj.get("list", [])
            all_accounts.extend(page_info)
            
            is_last_page = result_obj.get("isLastPage", True)
            print(f"[Mock] Page {page_num}: got {len(page_info)} accounts, isLastPage={is_last_page}")
            
            if is_last_page or not page_info:
                break
            page_num += 1

        return {
            "code": "0",
            "message": "成功",
            "resultObj": {
                "pageNum": 1,
                "pageSize": len(all_accounts),
                "total": len(all_accounts),
                "pages": 1,
                "isFirstPage": True,
                "isLastPage": True,
                "list": all_accounts
            }
        }
    except Exception as e:
        print(f"[Mock] CRM accounts error: {e}")
        return {"code": "-1", "message": str(e), "resultObj": None}


# ============ 销售品成员配置 ============
@app.post("/CCInter/open/offer/members")
async def query_offer_members(request: dict):
    """查询销售品成员配置"""
    prod_offer_id = request.get("prodOfferId", "")
    prod_list = request.get("prodOfferList", [])
    print(f"[Mock] query_offer_members called with prodOfferId: {prod_offer_id}")

    return {
        "code": "0",
        "message": "成功",
        "resultObj": [
            {
                "offerProdRelaId": 100082,
                "maxCount": 5,
                "minCount": 1,
                "productId": 100002902,
                "prodOfferId": 600002903,
                "offerVersionId": 3,
                "defaultCount": 1,
                "beId": "98d2186f6a6f407888457215cdd61c28",
                "firstFlag": False,
                "pkgProdOfferId": prod_offer_id or 600000004,
                "prodOfferName": "Mobile",
                "prodFuncTypeId": 1,
                "productName": "Mobile",
                "prodVersionId": 3,
                "accessTypeList": [
                    {
                        "prodAccessTypeId": 80000582,
                        "productId": 100002902,
                        "prodVersionId": 3,
                        "accessTypeId": 811,
                        "accessType": "Mobile",
                        "state": "1"
                    }
                ],
                "prodServiceList": [
                    {
                        "serviceOfferId": 2101,
                        "actionCd": "5101",
                        "productId": 100002902,
                        "prodOfferId": 600002903,
                        "offerServiceOfferId": 100060101,
                        "actionName": "新装",
                        "prodActionCd": "101"
                    }
                ]
            },
            {
                "offerProdRelaId": 100083,
                "maxCount": 6,
                "minCount": 1,
                "productId": 100000004,
                "prodOfferId": 609615487,
                "offerVersionId": 3,
                "defaultCount": 1,
                "beId": "98d2186f6a6f407888457215cdd61c28",
                "firstFlag": False,
                "pkgProdOfferId": prod_offer_id or 600000004,
                "prodOfferName": "CPE",
                "prodFuncTypeId": 1,
                "productName": "CPE",
                "prodVersionId": 3,
                "accessTypeList": [
                    {
                        "prodAccessTypeId": 80000589,
                        "productId": 100000004,
                        "prodVersionId": 3,
                        "accessTypeId": 830,
                        "accessType": "CPE",
                        "state": "1"
                    }
                ],
                "prodServiceList": [
                    {
                        "serviceOfferId": 4101,
                        "actionCd": "5101",
                        "productId": 100000004,
                        "prodOfferId": 609615487,
                        "offerServiceOfferId": 100060051,
                        "actionName": "新装",
                        "prodActionCd": "101"
                    }
                ]
            }
        ]
    }


# ============ 可选号码查询 ============
@app.post("/CCInter/open/offer/serviceNo")
async def query_service_numbers(request: dict):
    """查询可选号码"""
    project_code = request.get("projectCode", "")
    access_type = request.get("accessType", "")
    print(f"[Mock] query_service_numbers called with projectCode: {project_code}, accessType: {access_type}")

    # 生成模拟号码列表
    avail_numbers = []
    base_numbers = ["153", "188", "189", "199", "177"]
    for i in range(20):
        prefix = base_numbers[i % len(base_numbers)]
        avail_numbers.append({
            "mmeEid": 1004531 + i,
            "mmeVersion": 1,
            "code": f"{prefix}0000{i:04d}",
            "servicestatus": "1",
            "pageNum": 0,
            "pageSize": 0
        })

    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "availNumbers": avail_numbers,
            "preoccupyNumbers": []
        }
    }


# ============ 资源查询(ICCID) ============
@app.post("/CCInter/open/resource/query")
async def query_resources(request: dict):
    """查询ICCID资源"""
    root_category_id = request.get("rootCategoryId", "")
    category_id = request.get("categoryId", "")
    life_status = request.get("lifeStatus", "1")
    print(f"[Mock] query_resources called with categoryId: {category_id}")

    # 生成模拟ICCID列表
    iccid_list = []
    for i in range(10):
        iccid_list.append({
            "beId": "98d2186f6a6f407888457215cdd61c28",
            "resInvCode": f"202406131000{5857 + i:04d}",
            "categoryId": category_id or "CS10002",
            "categoryType": "Orderly",
            "modelId": "M10047",
            "brandId": "A10025",
            "resManufacturerId": 200001,
            "unit": 1003,
            "status": "1",
            "resStoreId": "1C697A5EB7907D410B253DC9630F148E",
            "skuId": "1C697A5EB7902CB50ABC9EA7215998A2",
            "version": 0,
            "lifeStatus": life_status,
            "resStoreName": "mola8STORE",
            "categoryName": "SIM Cards",
            "brandName": "Standard",
            "resManufactuerName": "HuaWei",
            "modelName": "SIM Cards1",
            "simInfo": {
                "resInvCode": f"202406131000{5857 + i:04d}",
                "cardType": "SIM",
                "iccid": f"8986000000000000{1498 + i:04d}",
                "imsi": f"46000000000{1498 + i:04d}",
                "comSupport": "1,2"
            },
            "skuName": "M-StandardSIM/3G/4G",
            "forIccid": True
        })

    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "pageNum": 1,
            "pageSize": 10,
            "total": 10,
            "pages": 1,
            "isFirstPage": True,
            "isLastPage": True,
            "list": iccid_list
        }
    }


# ============ 订单提交 ============
@app.post("/CCInter/open/order/submit")
async def submit_order(request: dict):
    """提交订单"""
    cust_id = request.get("custId", "")
    cust_name = request.get("custName", "")
    print(f"[Mock] submit_order called with custId: {cust_id}")

    # 生成订单ID
    order_id = f"10156307"
    import random
    order_id = f"10{random.randint(1000000, 9999999)}"

    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "pageSize": 5,
            "custOrderId": order_id,
            "feeItemDetailList": [
                {
                    "pageSize": 5,
                    "beId": "98d2186f6a6f407888457215cdd61c28",
                    "feeItemGuid": "9418828860C06ACD0C155C0EA08E5EE1",
                    "custOrderId": order_id,
                    "offerId": 600000004,
                    "offerName": "5G Smart Offer",
                    "feeItemId": 103,
                    "feeItemName": "选号费",
                    "feeType": "89J",
                    "allowNext": "1",
                    "taxRate": "15.00",
                    "moneyUnit": 1049,
                    "totalFee": "0.00",
                    "favorFee": "0.00",
                    "paidFee": "0.00",
                    "paymentMethod": "1",
                    "taxFee": "0.00",
                    "installGuid": "c4922eceb65d40c0814cd62be43620f5",
                    "state": "14",
                    "stateDate": datetime.now().strftime("%Y-%m-%d"),
                    "isNextPay": "1",
                    "serialNo": datetime.now().strftime("%Y%m%d%H%M%S") + "6579",
                    "allowPaidinCash": "1",
                    "paymentType": "2",
                    "feeItemCode": "103",
                    "principalFee": "0.00"
                }
            ],
            "hasResRecory": False
        }
    }


# ============ 费用查询 ============
@app.post("/CCInter/open/order/fee/query")
async def query_order_fee(request: dict):
    """订单费用查询/报价"""
    cust_id = request.get("custId", "")
    pkg_offer = request.get("pkgOffer", {})
    basic_offers = request.get("basicOffers", [])
    account_id = request.get("accountId", "")
    print(f"[Mock] query_order_fee called with custId: {cust_id}")

    offer_id = pkg_offer.get("offerId", 600000004)
    offer_name = "5G Smart Offer"

    # 查找主销售品名称
    all_offers = [
        {"prodOfferId": 600000004, "prodOfferName": "5G Smart Offer", "offerFeeDescription": "128元/月"},
        {"prodOfferId": 600003301, "prodOfferName": "CUG GROUP Offer", "offerFeeDescription": "88元/月"},
        {"prodOfferId": 600000003, "prodOfferName": "Mobile Offer", "offerFeeDescription": "58元/月"},
    ]
    for o in all_offers:
        if o["prodOfferId"] == offer_id:
            offer_name = o["prodOfferName"]
            break

    # 计算费用
    base_fee = 0.00
    number_fee = 0.00

    fee_items = []

    # 主套餐费用
    fee_items.append({
        "pageSize": 5,
        "beId": "98d2186f6a6f407888457215cdd61c28",
        "feeItemGuid": "9418828860C06ACD0C155C0EA08E5EE1",
        "custOrderId": "",
        "offerId": offer_id,
        "offerName": offer_name,
        "feeItemId": 101,
        "feeItemName": "套餐月租费",
        "feeType": "89J",
        "allowNext": "1",
        "taxRate": "15.00",
        "moneyUnit": 1031,
        "totalFee": "128.00",
        "favorFee": "0.00",
        "paidFee": "0.00",
        "paymentMethod": "1",
        "taxFee": "0.00",
        "state": "14",
        "stateDate": datetime.now().strftime("%Y-%m-%d"),
        "isNextPay": "1",
        "serialNo": datetime.now().strftime("%Y%m%d%H%M%S") + "0001",
        "allowPaidinCash": "1",
        "paymentType": "2",
        "feeItemCode": "101",
        "principalFee": "128.00"
    })

    # 选号费
    if basic_offers:
        for i, bo in enumerate(basic_offers):
            billing_no = bo.get("billingNo", "")
            if billing_no:
                fee_items.append({
                    "pageSize": 5,
                    "beId": "98d2186f6a6f407888457215cdd61c28",
                    "feeItemGuid": f"feeitem{1000+i}",
                    "custOrderId": "",
                    "offerId": bo.get("offerId", 0),
                    "offerName": "选号费",
                    "feeItemId": 103,
                    "feeItemName": "选号费 - " + billing_no,
                    "feeType": "89J",
                    "allowNext": "1",
                    "taxRate": "15.00",
                    "moneyUnit": 1031,
                    "totalFee": "0.00",
                    "favorFee": "0.00",
                    "paidFee": "0.00",
                    "paymentMethod": "1",
                    "taxFee": "0.00",
                    "state": "14",
                    "stateDate": datetime.now().strftime("%Y-%m-%d"),
                    "isNextPay": "1",
                    "serialNo": datetime.now().strftime("%Y%m%d%H%M%S") + f"{i:04d}",
                    "allowPaidinCash": "1",
                    "paymentType": "2",
                    "feeItemCode": "103",
                    "principalFee": "0.00"
                })

    total_fee = sum(float(f.get("totalFee", "0")) for f in fee_items)

    return {
        "code": "0",
        "message": "成功",
        "resultObj": {
            "pageSize": 5,
            "custOrderId": "",
            "feeItemDetailList": fee_items,
            "totalFee": str(total_fee),
            "hasResRecory": False
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
