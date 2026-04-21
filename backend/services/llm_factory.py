"""
LLM 工厂 - 支持多模型厂商
支持: MiniMax, DeepSeek, Kimi
"""
import os
import requests
from typing import List, Dict, Optional
import config


class BaseLLM:
    """LLM 基类"""
    
    def __init__(self, provider: str = None):
        self.provider = provider or config.DEFAULT_PROVIDER
        self.config = config.PROVIDERS.get(self.provider, config.PROVIDERS["minimax"])
        self.api_key = self.config.get("api_key", "")
        self.base_url = self.config.get("base_url", "")
        self.model = self.config.get("model", "")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 2048)
        
        if not self.api_key:
            raise ValueError(f"API Key 未配置: {self.provider}")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        raise NotImplementedError
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        raise NotImplementedError
    
    @property
    def llm(self):
        return self


class MiniMaxLLM(BaseLLM):
    """MiniMax 大模型"""
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self._call_api(messages)
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        return self._call_api(messages)
    
    def _call_api(self, messages: List[Dict]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/text/chatcompletion_v2",
                headers=headers,
                json=payload,
                timeout=60
            )
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            elif "error" in result:
                return f"API错误: {result['error']}"
            return "模型响应为空"
        except Exception as e:
            return f"请求失败: {str(e)}"


class DeepSeekLLM(BaseLLM):
    """DeepSeek 大模型"""
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self._call_api(messages)
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        return self._call_api(messages)
    
    def _call_api(self, messages: List[Dict]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            elif "error" in result:
                return f"API错误: {result['error']['message']}"
            return "模型响应为空"
        except Exception as e:
            return f"请求失败: {str(e)}"


class KimiLLM(BaseLLM):
    """Kimi 大模型"""
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self._call_api(messages)
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        return self._call_api(messages)
    
    def _call_api(self, messages: List[Dict]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            elif "error" in result:
                return f"API错误: {result['error']['message']}"
            return "模型响应为空"
        except Exception as e:
            return f"请求失败: {str(e)}"


# LLM 工厂函数
class LLMFactory:
    """LLM 工厂"""
    
    _providers = {
        "minimax": MiniMaxLLM,
        "deepseek": DeepSeekLLM,
        "kimi": KimiLLM
    }
    
    @classmethod
    def create(cls, provider: str = None) -> BaseLLM:
        """创建 LLM 实例"""
        provider = provider or config.DEFAULT_PROVIDER
        if provider not in cls._providers:
            raise ValueError(f"不支持的模型厂商: {provider}")
        return cls._providers[provider](provider)
    
    @classmethod
    def get_providers(cls) -> List[str]:
        """获取支持的厂商列表"""
        return list(cls._providers.keys())


# 兼容旧接口
class MiniMaxChatModel:
    """兼容旧版本的接口"""
    
    def __init__(self, api_key: str = None, model_name: str = "MiniMax-M2.1"):
        # 优先使用配置文件的配置
        self.api_key = api_key or config.PROVIDERS["minimax"]["api_key"]
        self.model_name = model_name
        self.llm = LLMFactory.create("minimax")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        return self.llm.chat(prompt, system_prompt)
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        return self.llm.chat_with_history(messages)


def create_llm(provider: str = None) -> BaseLLM:
    """创建 LLM 实例"""
    return LLMFactory.create(provider)


def create_llm_by_config(config_dict: dict) -> BaseLLM:
    """通过配置创建 LLM"""
    provider = config_dict.get("provider", config.DEFAULT_PROVIDER)
    llm_class = LLMFactory._providers.get(provider)
    if not llm_class:
        raise ValueError(f"不支持的厂商: {provider}")
    return llm_class(provider)