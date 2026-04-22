# CRM 业务系统配置
CRM_API_BASE_URL = "http://127.0.0.1:8001"

# 大模型配置
# 支持: minimax, deepseek, kimi

# 默认使用的大模型
DEFAULT_PROVIDER = "deepseek"

# 各模型配置
PROVIDERS = {
    "minimax": {
        "name": "MiniMax",
        "api_key": "",  # 请填入 API Key
        "base_url": "https://api.minimax.chat/v1",
        "model": "MiniMax-M2.1",
        "temperature": 0.7,
        "max_tokens": 2048
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_key": "sk-2bc0703468734baba05e5f3dd2162aa7",  # 请填入 DeepSeek API Key
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 2048
    },
    "kimi": {
        "name": "Kimi",
        "api_key": "",  # 请填入 Kimi API Key
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "temperature": 0.7,
        "max_tokens": 2048
    }
}

# 会话配置
SESSION_CONFIG = {
    "max_history": 20,      # 最大历史消息数
    "context_window": 10,     # 上下文窗口大小
    "session_timeout": 3600   # 会话超时时间（秒）
}