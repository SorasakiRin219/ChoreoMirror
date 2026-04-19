"""
AI 提供商模块，
包含调用不同 AI 提供商的函数
"""
import os

# 检测可选的依赖
HAS_ANTHROPIC = False
HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# AI 提供商默认配置
PROVIDER_DEFAULTS = {
    "anthropic": {"model": "claude-sonnet-4-20250514", "base_url": ""},
    "deepseek": {"model": "deepseek-chat", "base_url": "https://api.deepseek.com"},
    "openai": {"model": "gpt-4o", "base_url": ""},
    "qwen": {"model": "qwen-plus", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "doubao": {"model": "doubao-1-5-pro-32k-250115", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "zhipu": {"model": "glm-4-flash", "base_url": "https://open.bigmodel.cn/api/paas/v4/"},
    "kimi": {"model": "moonshot-v1-8k", "base_url": "https://api.moonshot.cn/v1"},
    "ollama": {"model": "qwen2.5:7b", "base_url": "http://localhost:11434/v1"},
}


def call_ai(ts_result: dict, hist_a: list, hist_b: list,
            sym_a: dict, sym_b: dict, extra: str = "") -> str:
    """
    调用 AI 提供商获取舞蹈分析建议
    Args:
        ts_result: 时序对比结果
        hist_a: 侧 A 历史数据
        hist_b: 侧 B 历史数据
        sym_a: 侧 A 对称性分析
        sym_b: 侧 B 对称性分析
        extra: 补充说明
    Returns:
        AI 分析建议字符串
    """
    from .prompts import build_prompt_ts
    from web.app import get_state

    STATE = get_state()
    provider = STATE.provider
    key = STATE.api_keys.get(provider, "")
    model = STATE.model
    base_url = STATE.base_url
    prompt = build_prompt_ts(ts_result, hist_a, hist_b, sym_a, sym_b, extra)

    if not key and provider != "ollama":
        return f"⚠ 请在「AI 设置」中填入 {provider} 的 API Key"

    if provider == "anthropic":
        if not HAS_ANTHROPIC:
            return "❌ pip install anthropic"
        try:
            c = anthropic.Anthropic(api_key=key)
            m = c.messages.create(
                model=model or PROVIDER_DEFAULTS["anthropic"]["model"],
                max_tokens=1400,
                messages=[{"role": "user", "content": prompt}]
            )
            return m.content[0].text
        except Exception as e:
            return f"❌ Anthropic: {e}"

    if provider in ("deepseek", "openai", "qwen", "doubao", "zhipu", "kimi", "ollama"):
        if not HAS_OPENAI:
            return "❌ pip install openai"
        try:
            defs = PROVIDER_DEFAULTS.get(provider, {})
            url = base_url or defs.get("base_url") or None
            mdl = model or defs.get("model", "gpt-4o")
            kw = {"api_key": key if key else "ollama"}
            if url:
                kw["base_url"] = url
            c = openai.OpenAI(**kw)
            r = c.chat.completions.create(
                model=mdl,
                max_tokens=1400,
                messages=[{"role": "user", "content": prompt}]
            )
            return r.choices[0].message.content
        except Exception as e:
            return f"❌ {provider}: {e}"

    return f"❌ 未知提供商: {provider}"
