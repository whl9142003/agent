"""
Internationalization support module
Supports: Chinese(zh), English(en), French(fr)
"""
from typing import Dict, Optional

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh": {
        "welcome": "欢迎使用营业受理机器人",
        "authenticated": "已认证",
        "unauthenticated": "未认证",
        "login_success": "认证成功",
        "login_failed": "认证失败",
        "order_inquiry": "订单查询",
        "product_inquiry": "产品查询",
        "no_offers": "暂无订购销售品",
        "product_name": "产品名称",
        "billing_no": "账单号码",
        "contract_no": "合同号码",
        "effective_time": "生效时间",
        "expiration_time": "失效时间",
        "status": "状态",
        "active": "生效中",
        "expired": "已失效",
        "pending": "待生效",
        "customer_name": "客户姓名",
        "phone": "手机号",
        "account_balance": "账户余额",
        "current_package": "当前套餐",
        "order_status": "订单状态",
        "order_no": "订单号",
        "order_date": "订购时间",
        "no_data": "暂无",
        "processing": "正在处理...",
        "error_occurred": "处理您的请求时发生错误",
        "network_error": "网络错误，请检查连接后重试",
        "dear_user": "尊敬的用户",
        "hello": "您好",
        "your_orders": "您名下的订单",
        "your_products": "您名下的产品",
    },
    "en": {
        "welcome": "Welcome to Business Service Robot",
        "authenticated": "Authenticated",
        "unauthenticated": "Not Authenticated",
        "login_success": "Authentication Successful",
        "login_failed": "Authentication Failed",
        "order_inquiry": "Order Inquiry",
        "product_inquiry": "Product Inquiry",
        "no_offers": "No subscribed products",
        "product_name": "Product Name",
        "billing_no": "Billing Number",
        "contract_no": "Contract Number",
        "effective_time": "Effective Time",
        "expiration_time": "Expiration Time",
        "status": "Status",
        "active": "Active",
        "expired": "Expired",
        "pending": "Pending",
        "customer_name": "Customer Name",
        "phone": "Phone Number",
        "account_balance": "Account Balance",
        "current_package": "Current Package",
        "order_status": "Order Status",
        "order_no": "Order Number",
        "order_date": "Order Date",
        "no_data": "N/A",
        "processing": "Processing...",
        "error_occurred": "An error occurred while processing your request",
        "network_error": "Network error, please check your connection",
        "dear_user": "Dear Customer",
        "hello": "Hello",
        "your_orders": "Your Orders",
        "your_products": "Your Products",
    },
    "fr": {
        "welcome": "Bienvenue au Robot de Service Commercial",
        "authenticated": "Authentifie",
        "unauthenticated": "Non Authentifie",
        "login_success": "Authentification Reussie",
        "login_failed": "Authentification Echouee",
        "order_inquiry": "Demande de Commande",
        "product_inquiry": "Demande de Produit",
        "no_offers": "Aucun produit abonne",
        "product_name": "Nom du Produit",
        "billing_no": "Numero de Facturation",
        "contract_no": "Numero de Contrat",
        "effective_time": "Date d'Effet",
        "expiration_time": "Date d'Expiration",
        "status": "Statut",
        "active": "Actif",
        "expired": "Expire",
        "pending": "En Attente",
        "customer_name": "Nom du Client",
        "phone": "Numero de Telephone",
        "account_balance": "Solde du Compte",
        "current_package": "Forfait Actuel",
        "order_status": "Statut de Commande",
        "order_no": "Numero de Commande",
        "order_date": "Date de Commande",
        "no_data": "N/A",
        "processing": "Traitement en cours...",
        "error_occurred": "Une erreur s'est produite lors du traitement",
        "network_error": "Erreur reseau, veuillez verifier votre connexion",
        "dear_user": "Cher Client",
        "hello": "Bonjour",
        "your_orders": "Vos Commandes",
        "your_products": "Vos Produits",
    }
}


def get_translations(language: str = "zh") -> Dict[str, str]:
    """Get translations for specified language"""
    return TRANSLATIONS.get(language, TRANSLATIONS["zh"])


def t(key: str, language: str = "zh") -> str:
    """Translate single key"""
    translations = get_translations(language)
    return translations.get(key, TRANSLATIONS["zh"].get(key, key))


def format_message(message: str, language: str = "zh") -> str:
    """Format message template based on language"""
    translations = get_translations(language)
    replacements = {
        "{dear_user}": translations["dear_user"],
        "{hello}": translations["hello"],
        "{no_offers}": translations["no_offers"],
        "{no_data}": translations["no_data"],
    }
    result = message
    for placeholder, replacement in replacements.items():
        result = result.replace(placeholder, replacement)
    return result


def format_offers_for_language(offers: list, language: str = "zh") -> str:
    """Format offers info based on language"""
    translations = get_translations(language)
    if not offers:
        return translations["no_offers"]

    lines = []
    for offer in offers:
        offer_name = offer.get("offerName", translations["no_data"])
        billing_no = offer.get("billingNo", translations["no_data"])
        contract_cd = offer.get("contractCd", translations["no_data"])
        eff_date = offer.get("effDate", translations["no_data"])
        exp_date = offer.get("expDate", translations["no_data"])

        eff_str = _format_date(eff_date, translations["no_data"])
        exp_str = _format_date(exp_date, translations["no_data"])

        lines.append(f"📦 {offer_name}")
        lines.append(f"   {translations['billing_no']}：{billing_no}")
        lines.append(f"   {translations['contract_no']}：{contract_cd}")
        lines.append(f"   {translations['effective_time']}：{eff_str}")
        lines.append(f"   {translations['expiration_time']}：{exp_str}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_date(date_str: Optional[str], no_data: str = "暂无") -> str:
    """Format date string"""
    if not date_str or date_str == no_data or date_str == "N/A":
        return no_data
    if len(date_str) == 10 and "-" in date_str:
        return date_str
    return date_str


def get_auth_badge_text(authenticated: bool, customer_name: Optional[str], language: str = "zh") -> str:
    """Get auth badge text"""
    translations = get_translations(language)
    if authenticated:
        if customer_name:
            return f"{customer_name} {translations['authenticated']}"
        return translations["authenticated"]
    return translations["unauthenticated"]