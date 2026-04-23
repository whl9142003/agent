"""
DeepSeek LLM Service
使用 DeepSeek API 进行对话
"""
import os
import requests
from typing import Optional, List, Dict, Any


class DeepSeekChatModel:
    """DeepSeek 对话模型"""

    def __init__(self, api_key: str = None, model_name: str = "deepseek-chat"):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "sk-2bc0703468734baba05e5f3dd2162aa7")
        self.model_name = model_name
        self.api_base = "https://api.deepseek.com/v1"
        self.temperature = 0.7
        self.max_tokens = 2048

        if not self.api_key:
            print("警告: 未设置DEEPSEEK_API_KEY环境变量")

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

    def invoke(self, prompt: str) -> Any:
        """LangChain 兼容的 invoke 方法"""
        class InvokeResult:
            def __init__(self, content):
                self.content = content
        result = self.chat(prompt)
        return InvokeResult(result)

    def _call_api(self, messages: List[Dict]) -> str:
        """调用DeepSeek API"""
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
                f"{self.api_base}/chat/completions",
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


def create_deepseek_llm(api_key: str = None, model: str = "deepseek-chat") -> DeepSeekChatModel:
    """创建DeepSeek LLM实例的工厂函数"""
    return DeepSeekChatModel(api_key=api_key, model_name=model)