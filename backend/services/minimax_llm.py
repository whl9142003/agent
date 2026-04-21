"""
MiniMax LLM Service - Chat兼容版本
支持 LangChain 调用（作为 chat model）
"""
import os
import requests
from typing import Optional, List, Dict, Any


class MiniMaxChatModel:
    """MiniMax 对话模型 - LangChain ChatModel 兼容版本"""

    def __init__(self, api_key: str = "sk-cp-IESAM4xsZvAn_S0ZqbZF2LRX19gDH1_D5F_H14nAFkVlSVh1wYQoGuqa_UhHfvQPHklqgQEluJbiyn_x_9i7KFT0HaWJFRNoQ6SCum1_QMqIkhxzOnQ2TY8", model_name: str = "MiniMax-M2.1"):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.model_name = model_name
        self.api_base = "https://api.minimax.chat/v1"
        self.temperature = 0.7
        self.max_tokens = 2048

        if not self.api_key:
            print("警告: 未设置MINIMAX_API_KEY环境变量")
        
        # 设置为 LangChain 兼容的 llm 属性
        self.llm = self  # 自身作为 LangChain LLM

    def __call__(self, messages: List[Dict[str, str]]) -> str:
        """LangChain ChatModel 接口"""
        return self.chat_with_history(messages)

    def chat(self, prompt: str, system_prompt: str = None) -> str:
        """单轮对话"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self._call_api(messages)

    def chat_with_history(self, messages: List[Dict[str, str]]) -> str:
        """多轮对话"""
        return self._call_api(messages)

    def _call_api(self, messages: List[Dict]) -> str:
        """调用MiniMax API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        try:
            response = requests.post(
                f"{self.api_base}/text/chatcompletion_v2",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            elif "error" in result:
                return f"API错误: {result['error']}"
            else:
                return "模型响应为空"

        except requests.exceptions.Timeout:
            return "请求超时，请稍后重试"
        except requests.exceptions.RequestException as e:
            return f"请求失败: {str(e)}"
        except Exception as e:
            return f"发生错误: {str(e)}"

    def bind(self, **kwargs):
        """LangChain bind 方法"""
        return self


def create_llm(api_key: str = None, model: str = "MiniMax-M2.1") -> MiniMaxChatModel:
    """创建LLM实例的工厂函数"""
    return MiniMaxChatModel(api_key=api_key, model_name=model)
