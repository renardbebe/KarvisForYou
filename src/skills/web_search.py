# -*- coding: utf-8 -*-
"""
Skill: web.search
实时信息检索 — 基于阿里云百炼 Qwen API 的 enable_search 联网搜索。

场景：
- LLM 对用户提到的歌曲/电影/书籍/人物/事件不确定时
- 用户询问实时信息（新闻、价格、赛事、天气细节等）
- 用户分享的内容疑似歌词/台词/引用，需要确认出处
- 任何 LLM 训练数据可能没有覆盖的知识

原理：
- 调用 Qwen API 的 enable_search=true 模式
- Qwen 内部联网检索后返回有据可查的信息
- 搜索结果注入上下文，再由主模型生成最终回复
"""
import sys
import requests
from config import QWEN_API_KEY, QWEN_BASE_URL

# 联网搜索使用更强的模型以获得更好的搜索理解
_SEARCH_MODEL = "qwen-plus"


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def search(params, state, ctx):
    """
    web.search — 联网搜索获取实时信息。

    params:
        query: str — 搜索查询（由 LLM 根据用户消息生成）
        context: str — 可选，用户原始消息（帮助搜索理解上下文）
    """
    query = (params.get("query") or "").strip()
    if not query:
        return {"success": False, "reply": "需要搜索内容"}

    user_context = (params.get("context") or "").strip()

    # 构建搜索 prompt：让 Qwen 联网搜索后返回结构化信息
    search_prompt = f"""请联网搜索以下内容，返回准确、有据可查的信息。

搜索查询：{query}"""

    if user_context:
        search_prompt += f"\n用户原始消息：{user_context}"

    search_prompt += """

要求：
1. 返回搜索到的核心事实信息（简洁准确，不要废话）
2. 如果是歌曲/电影/书籍，包含：名称、创作者、年份、简介
3. 如果是歌词/台词，确认出处（哪首歌/哪部作品的哪个段落）
4. 如果是新闻/时事，包含：事件概述、时间、关键细节
5. 如果搜索不到明确结果，如实说明"""

    result = _call_qwen_search(search_prompt)

    if not result:
        return {
            "success": False,
            "reply": "联网搜索暂时不可用，稍后再试~"
        }

    _log(f"[web.search] query={query}, result_len={len(result)}")

    return {
        "success": True,
        "search_result": result,
        # 不直接 reply —— 让 brain.py 的 Agent Loop 拿到搜索结果后
        # 再由主模型结合上下文生成自然回复
    }


def _call_qwen_search(prompt, max_tokens=800, temperature=0.3):
    """
    调用阿里云百炼 Qwen API（enable_search=true）进行联网搜索。

    使用 qwen-plus 模型以获得更好的搜索理解能力。
    """
    url = f"{QWEN_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": _SEARCH_MODEL,
        "messages": [
            {"role": "system", "content": "你是一个信息检索助手。联网搜索后返回准确、简洁的事实信息。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "enable_search": True,
    }

    try:
        _log(f"[web.search] Qwen联网搜索: model={_SEARCH_MODEL}, prompt_len={len(prompt)}")
        resp = requests.post(url, headers=headers, json=data, timeout=20)

        if resp.status_code == 200:
            result = resp.json()
            usage = result.get("usage", {})
            content = result["choices"][0]["message"]["content"]
            _log(f"[web.search] Qwen搜索完成: "
                 f"prompt_tokens={usage.get('prompt_tokens')}, "
                 f"completion_tokens={usage.get('completion_tokens')}, "
                 f"result_len={len(content)}")
            return content

        _log(f"[web.search] Qwen API 错误: {resp.status_code} - {resp.text[:200]}")
        return None

    except Exception as e:
        _log(f"[web.search] Qwen联网搜索失败: {e}")
        return None


# ============ Skill 热加载注册表 ============
SKILL_REGISTRY = {
    "web.search": search,
}
