"""
知识库管理
用于存储和管理业务知识，提供检索增强
"""
import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path


class KnowledgeBase:
    """知识库"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "knowledge")
        self.products: Dict[str, Dict] = {}
        self.status_map: Dict[str, str] = {}
        self.packages: Dict[str, str] = {}
        self.faqs: List[Dict] = []
        self._load_knowledge()
    
    def _load_knowledge(self):
        """加载知识库数据"""
        # 产品映射
        self.products = {
            "5G畅享128": {
                "name": "5G畅享128元套餐",
                "price": 128,
                "data_quota": "30GB",
                "voice_quota": "500分钟",
                "description": "适合轻度流量用户"
            },
            "5G畅享198": {
                "name": "5G畅享198元套餐",
                "price": 198,
                "data_quota": "60GB",
                "voice_quota": "1000分钟",
                "description": "适合中度流量用户"
            },
            "5G畅享298": {
                "name": "5G畅享298元套餐",
                "price": 298,
                "data_quota": "150GB",
                "voice_quota": "无限",
                "description": "适合重度流量用户"
            }
        }
        
        # 订单状态映射
        self.status_map = {
            "pending_payment": "待支付",
            "paid": "已支付",
            "processing": "处理中",
            "completed": "已完成",
            "cancelled": "已取消",
            "shipped": "已发货",
            "active": "已激活"
        }
        
        # 套餐映射
        self.packages = {
            "5G畅享": "5G畅享套餐",
            "不限量": "不限量套餐",
            "畅享": "畅享套餐"
        }
        
        # 加载知识库文件
        self._load_files()
    
    def _load_files(self):
        """加载知识库文件"""
        knowledge_file = os.path.join(self.data_dir, "data.json")
        if os.path.exists(knowledge_file):
            try:
                with open(knowledge_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "products" in data:
                        self.products.update(data["products"])
                    if "status_map" in data:
                        self.status_map.update(data["status_map"])
                    if "packages" in data:
                        self.packages.update(data["packages"])
                    if "faqs" in data:
                        self.faqs = data["faqs"]
            except Exception as e:
                print(f"加载知识库文件失败: {e}")
    
    def get_product_info(self, keyword: str) -> Optional[Dict]:
        """获取产品信息"""
        keyword = keyword.lower()
        
        # 精确匹配
        if keyword in self.products:
            return self.products[keyword]
        
        # 模糊匹配
        for key, info in self.products.items():
            if keyword in key.lower() or keyword in info.get("name", "").lower():
                return {"key": key, **info}
        
        return None
    
    def get_status_text(self, status: str) -> str:
        """获取状态文本"""
        return self.status_map.get(status, status)
    
    def map_status(self, status_list: List[Dict]) -> List[Dict]:
        """映射订单状态"""
        for order in status_list:
            status = order.get("status", "")
            order["status_text"] = self.get_status_text(status)
        return status_list
    
    def format_product(self, products: List[Dict]) -> List[Dict]:
        """格式化产品信息"""
        formatted = []
        for p in products:
            name = p.get("name", "")
            # 映射产品信息
            product_info = self.get_product_info(name)
            if product_info:
                p["display_name"] = product_info.get("name", name)
                p["data_quota"] = product_info.get("data_quota", p.get("data_quota", ""))
                p["voice_quota"] = product_info.get("voice_quota", p.get("voice_quota", ""))
                p["description"] = product_info.get("description", p.get("description", ""))
            formatted.append(p)
        return formatted
    
    def search_faq(self, question: str) -> Optional[str]:
        """搜索 FAQ"""
        question_lower = question.lower()
        for faq in self.faqs:
            keywords = faq.get("keywords", [])
            if any(kw in question_lower for kw in keywords):
                return faq.get("answer", "")
        return None
    
    def enhance_response(self, response_type: str, data: Any) -> Dict:
        """增强响应数据"""
        if response_type == "products":
            # 格式化产品列表
            if isinstance(data, list):
                return {
                    "success": True,
                    "products": self.format_product(data),
                    "total": len(data)
                }
        
        elif response_type == "orders":
            # 映射订单状态
            if isinstance(data, list):
                return {
                    "success": True,
                    "orders": self.map_status(data),
                    "total": len(data)
                }
        
        elif response_type == "status":
            # 单个状态映射
            return {
                "success": True,
                "status": data,
                "display": self.get_status_text(data)
            }
        
        return {"success": True, "data": data}


# 全局知识库实例
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """获取知识库实例"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


def reload_knowledge():
    """重新加载知识库"""
    global _knowledge_base
    _knowledge_base = KnowledgeBase()