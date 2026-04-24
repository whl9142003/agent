"""
CRM业务知识库 - 编码字段中文映射
"""

# 产品/销售品类型映射
PRODUCT_OFFER_TYPE_MAP = {
    "1": "移动语音",
    "2": "数据流量",
    "3": "短信",
    "4": "彩信",
    "5": "增值业务",
    "6": "基础套餐",
    "7": "组合套餐",
    "8": "合约套餐",
    "9": "月租套餐",
    "10": "日租套餐",
    "11": "流量包",
    "12": "语音包",
    "13": "短彩包",
    "14": "国际业务",
    "15": "港澳台业务",
    "16": "漫游业务",
    "17": "融合业务",
    "18": "宽带业务",
    "19": "IPTV",
    "20": "固话业务",
    "21": "集团业务",
    "22": "物联网",
    "23": "eSIM",
    "24": "亲情网",
    "25": "家庭网",
}

# 自动续费状态映射
AUTO_RENEW_MAP = {
    "1": "自动续费",
    "2": "到期不续",
    "3": "到期自动取消",
    "true": "自动续费",
    "false": "到期不续",
    "Y": "自动续费",
    "N": "到期不续",
    "A": "自动续费",
    "C": "到期不续",
}

# 状态映射
STATUS_MAP = {
    "1": "生效中",
    "2": "暂停",
    "3": "注销",
    "4": "预销户",
    "5": "待生效",
    "6": "已失效",
    "7": "冻结",
    "A": "生效中",
    "S": "暂停",
    "D": "注销",
}

# 品牌映射
BRAND_MAP = {
    "1": "全球通",
    "2": "神州行",
    "3": "动感地带",
    "4": "移动王卡",
    "5": "移动花卡",
}

# 账户类型映射
ACCOUNT_TYPE_MAP = {
    "1": "个人账户",
    "2": "家庭账户",
    "3": "集团账户",
    "4": "政府账户",
}

# 客户类型映射
CUSTOMER_TYPE_MAP = {
    "1": "普通客户",
    "2": "VIP客户",
    "3": "集团客户",
    "4": "战略客户",
    "P": "个人客户",
    "C": "企业客户",
}

# 套餐档位映射
PACKAGE_TIER_MAP = {
    "1": "基础档",
    "2": "标准档",
    "3": "高级档",
    "4": "旗舰档",
    "5": "尊享档",
}


def get_product_offer_type_name(code: str) -> str:
    """获取产品销售品类型名称"""
    if not code:
        return "未知类型"
    return PRODUCT_OFFER_TYPE_MAP.get(str(code), f"类型{code}")


def get_auto_renew_name(code: str) -> str:
    """获取自动续费状态名称"""
    if not code:
        return "未知"
    return AUTO_RENEW_MAP.get(str(code), AUTO_RENEW_MAP.get(code, "未知"))


def get_status_name(code: str) -> str:
    """获取状态名称"""
    if not code:
        return "未知状态"
    return STATUS_MAP.get(str(code), STATUS_MAP.get(code, f"状态{code}"))


def get_brand_name(code: str) -> str:
    """获取品牌名称"""
    if not code:
        return "未知品牌"
    return BRAND_MAP.get(str(code), f"品牌{code}")


def get_customer_type_name(code: str) -> str:
    """获取客户类型名称"""
    if not code:
        return "未知"
    return CUSTOMER_TYPE_MAP.get(str(code), CUSTOMER_TYPE_MAP.get(code, f"类型{code}"))