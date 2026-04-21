# 大模型配置
# 支持: minimax, deepseek, kimi

# 默认使用的大模型
DEFAULT_PROVIDER = "minimax"

# 各模型配置
PROVIDERS = {
    "minimax": {
        "name": "MiniMax",
        "api_key": "sk-cp-IESAM4xsZvAn_S0ZqbZF2LRX19gDH1_D5F_H14nAFkVlSVh1wYQoGuqa_UhHfvQPHklqgQEluJbiyn_x_9i7KFT0HaWJFRNoQ6SCum1_QMqIkhxzOnQ2TY8",  # 请填入 API Key
        "base_url": "https://api.minimax.chat/v1",
        "model": "MiniMax-M2.1",
        "temperature": 0.7,
        "max_tokens": 2048
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_key": "",  # 请填入 DeepSeek API Key
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