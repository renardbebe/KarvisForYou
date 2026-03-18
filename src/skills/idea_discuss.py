# -*- coding: utf-8 -*-
"""
Skill: discuss.*
想法讨论/辩论 — 围绕用户的想法进行多轮有来有往的讨论。

工作方式：
1. 用户提出一个想法并希望讨论/辩论 → discuss.start（进入讨论模式）
2. 讨论中用户继续发消息 → discuss.reply（围绕话题深入交流）
3. 用户表示讨论结束/想要结论 → discuss.conclude（沉淀结论并归档）
4. 用户想放弃讨论 → discuss.cancel

讨论模式下 Karvis 的角色：
- 不是简单附和，而是提出不同角度、指出逻辑漏洞、给出延伸思考
- 态度友善但观点犀利，像一个聪明的辩友
- 跟踪讨论上下文，不重复已讨论过的点

state 字段：
    discuss_pending: bool — 是否处于讨论模式
    discuss_topic: str — 讨论话题
    discuss_history: list[{"role": str, "content": str}] — 讨论历史
    discuss_started_at: str — 开始时间
"""
import sys
import json
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


# ============ 讨论 AI Prompt ============

DISCUSS_SYSTEM = """你是用户的讨论伙伴。你们正在围绕一个话题进行深入讨论。

你的角色：
- 不是简单附和或赞同，而是一个**有独立思考能力的辩友**
- 主动提出不同角度、指出逻辑漏洞、给出延伸思考
- 态度友善但观点犀利 — 可以反驳，但要有理有据
- 当用户说得有道理时，坦诚认可并在此基础上延伸
- 每次回复聚焦 1-2 个要点，不要一次性把话说尽

讨论技巧：
- 苏格拉底式提问：用问题引导用户深入思考
- 钢铁人论证：先把对方的观点做到最强，再指出潜在问题
- 提供具体例子或反例来支撑你的观点
- 如果话题涉及长期记忆中的信息，主动结合

回复规则：
- 2-5 句话，简洁有力
- 不要用"你说得对，但是..."这种敷衍转折
- 不要每次都以问题结尾，有时候直接给出你的判断
- 语气温暖但不失锐度，像一个靠谱的好朋友在认真和你聊
- 直接输出回复文本，不要 JSON 格式"""

CONCLUDE_SYSTEM = """你是讨论总结助手。根据下面的讨论历史，提炼出结论。

输出 JSON（不要 markdown 代码块标记）：
{
  "title": "5-15字的讨论主题标题",
  "summary": "2-3句话概括讨论的核心过程和结果",
  "conclusion": "讨论得出的结论或共识（如果没有共识，说明分歧点）",
  "key_insights": ["洞察1", "洞察2"],
  "open_questions": ["如果有未解决的问题，列在这里"]
}"""


# ============ Skill 入口函数 ============

def start(params, state, ctx):
    """
    开始讨论。

    params:
        topic: str — 讨论话题/用户的初始想法
        stance: str — 可选，用户的立场
    """
    topic = (params.get("topic") or "").strip()
    stance = (params.get("stance") or "").strip()

    if not topic:
        return {"success": False, "reply": "想讨论什么话题呢？把你的想法告诉我~"}

    # 如果已经在讨论中，提示
    if state.get("discuss_pending"):
        old_topic = state.get("discuss_topic", "")
        return {
            "success": True,
            "reply": f"我们正在讨论「{old_topic}」呢~ 想切换话题的话，可以说'结束讨论'先收尾，或者说'取消讨论'直接换~"
        }

    now = datetime.now(BEIJING_TZ)

    # 构建初始讨论历史
    initial_content = topic
    if stance:
        initial_content = f"{topic}\n\n我的立场是：{stance}"

    history = [{"role": "user", "content": initial_content}]

    # 生成第一轮讨论回复
    first_reply = _generate_discuss_reply(topic, history, state, ctx)

    if first_reply:
        history.append({"role": "assistant", "content": first_reply})

    return {
        "success": True,
        "reply": first_reply or "这个话题很有意思，你能再详细说说你的想法吗？",
        "state_updates": {
            "discuss_pending": True,
            "discuss_topic": topic,
            "discuss_history": history,
            "discuss_started_at": now.strftime("%Y-%m-%d %H:%M"),
        }
    }


def reply(params, state, ctx):
    """
    讨论中的用户回复。

    params:
        message: str — 用户的回复内容
    """
    if not state.get("discuss_pending"):
        return {"success": False, "reply": "当前没有进行中的讨论"}

    message = (params.get("message") or "").strip()
    if not message:
        return {"success": True, "reply": "你想说什么呢？继续~"}

    topic = state.get("discuss_topic", "")
    history = state.get("discuss_history", [])[:]

    # 添加用户消息
    history.append({"role": "user", "content": message})

    # 生成讨论回复
    ai_reply = _generate_discuss_reply(topic, history, state, ctx)

    if ai_reply:
        history.append({"role": "assistant", "content": ai_reply})

    # 限制历史长度（保留最近 20 轮）
    if len(history) > 40:
        history = history[:2] + history[-38:]

    return {
        "success": True,
        "reply": ai_reply or "嗯，这个点我需要想想...",
        "state_updates": {
            "discuss_history": history,
        }
    }


def conclude(params, state, ctx):
    """
    结束讨论，生成结论并归档。

    params:
        extra_note: str — 可选，用户的额外补充
    """
    if not state.get("discuss_pending"):
        return {"success": True, "reply": "当前没有进行中的讨论哦"}

    topic = state.get("discuss_topic", "")
    history = state.get("discuss_history", [])
    extra_note = (params.get("extra_note") or "").strip()

    if len(history) < 2:
        # 讨论太短，直接结束
        return {
            "success": True,
            "reply": "讨论还没深入就结束了~下次有想法随时找我~",
            "state_updates": {
                "discuss_pending": False,
                "discuss_topic": "",
                "discuss_history": [],
                "discuss_started_at": "",
            }
        }

    # 生成结论
    conclusion = _generate_conclusion(topic, history, extra_note)

    # 归档到 work 分类
    archive_reply = _archive_discussion(topic, history, conclusion, ctx)

    # 构建用户回复
    if conclusion:
        title = conclusion.get("title", topic)
        summary = conclusion.get("summary", "")
        conclusion_text = conclusion.get("conclusion", "")
        insights = conclusion.get("key_insights", [])
        open_qs = conclusion.get("open_questions", [])

        reply_parts = [f"📝 讨论总结：「{title}」\n"]
        if summary:
            reply_parts.append(summary)
        if conclusion_text:
            reply_parts.append(f"\n💡 结论：{conclusion_text}")
        if insights:
            reply_parts.append("\n🔍 关键洞察：")
            for i, ins in enumerate(insights, 1):
                reply_parts.append(f"  {i}. {ins}")
        if open_qs:
            reply_parts.append("\n❓ 待探讨：")
            for q in open_qs:
                reply_parts.append(f"  · {q}")
        reply_parts.append("\n已帮你记下来了~")
        final_reply = "\n".join(reply_parts)
    else:
        final_reply = f"讨论「{topic}」到此结束~ 已经帮你归档了。"

    return {
        "success": True,
        "reply": final_reply,
        "state_updates": {
            "discuss_pending": False,
            "discuss_topic": "",
            "discuss_history": [],
            "discuss_started_at": "",
        }
    }


def cancel_discuss(params, state, ctx):
    """取消讨论。"""
    if not state.get("discuss_pending"):
        return {"success": True, "reply": "当前没有在讨论哦~"}

    topic = state.get("discuss_topic", "")
    return {
        "success": True,
        "reply": f"好的，「{topic}」的讨论先到这里~ 下次想继续随时找我~",
        "state_updates": {
            "discuss_pending": False,
            "discuss_topic": "",
            "discuss_history": [],
            "discuss_started_at": "",
        }
    }


# ============ AI 调用 ============

def _generate_discuss_reply(topic, history, state, ctx):
    """调用 LLM 生成讨论回复"""
    from brain import call_llm
    from memory import load_memory

    # 构建 system prompt（包含长期记忆的上下文）
    memory = load_memory(ctx)
    system_parts = [DISCUSS_SYSTEM]
    system_parts.append(f"\n## 讨论话题\n{topic}")
    if memory:
        # 只取前 500 字的记忆，避免太长
        system_parts.append(f"\n## 用户背景（长期记忆摘要）\n{memory[:500]}")
    system_prompt = "\n".join(system_parts)

    # 构建对话历史
    messages = [{"role": "system", "content": system_prompt}]
    # 只传最近 10 轮对话给 LLM，避免 token 超限
    recent_history = history[-20:] if len(history) > 20 else history
    messages.extend(recent_history)

    try:
        response = call_llm(messages, model_tier="main", max_tokens=400,
                           temperature=0.6)
        if response:
            _log(f"[discuss] 回复生成: {response[:60]}...")
        return response
    except Exception as e:
        _log(f"[discuss] AI 回复生成失败: {e}")
        return None


def _generate_conclusion(topic, history, extra_note=""):
    """调用 LLM 生成讨论结论"""
    from brain import call_llm

    # 构建对话摘要（最多取最近 15 轮）
    recent = history[-30:] if len(history) > 30 else history
    dialogue_parts = []
    for msg in recent:
        role_label = "用户" if msg["role"] == "user" else "Karvis"
        dialogue_parts.append(f"【{role_label}】{msg['content']}")
    dialogue = "\n\n".join(dialogue_parts)

    user_prompt = f"讨论话题：{topic}\n\n讨论记录：\n{dialogue}"
    if extra_note:
        user_prompt += f"\n\n用户补充说明：{extra_note}"

    try:
        response = call_llm([
            {"role": "system", "content": CONCLUDE_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], model_tier="main", max_tokens=500, temperature=0.4)

        if not response:
            return None

        # 解析 JSON
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except Exception:
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    return json.loads(text[start_idx:end_idx + 1])
                except Exception:
                    pass
        _log(f"[discuss] 结论 JSON 解析失败: {text[:200]}")
        return None
    except Exception as e:
        _log(f"[discuss] 结论生成失败: {e}")
        return None


def _archive_discussion(topic, history, conclusion, ctx):
    """将讨论内容归档到工作笔记"""
    now = datetime.now(BEIJING_TZ)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M")

    # 构建归档内容
    parts = [f"### 💬 讨论：{topic}", ""]

    if conclusion:
        if conclusion.get("summary"):
            parts.append(f"**摘要**：{conclusion['summary']}")
        if conclusion.get("conclusion"):
            parts.append(f"**结论**：{conclusion['conclusion']}")
        if conclusion.get("key_insights"):
            parts.append("**关键洞察**：")
            for ins in conclusion["key_insights"]:
                parts.append(f"- {ins}")
        if conclusion.get("open_questions"):
            parts.append("**待探讨**：")
            for q in conclusion["open_questions"]:
                parts.append(f"- {q}")
        parts.append("")

    # 附上精简的讨论过程
    parts.append("<details><summary>讨论过程</summary>\n")
    for msg in history:
        role_label = "🙋 我" if msg["role"] == "user" else "🤖 Karvis"
        content = msg["content"]
        if len(content) > 150:
            content = content[:150] + "..."
        parts.append(f"**{role_label}**：{content}\n")
    parts.append("</details>")

    parts.extend([f"*— {time_str}*", "", "---", ""])
    entry = "\n".join(parts)

    # 写入工作笔记
    file_path = f"{ctx.work_notes_dir}/{date_str}.md"
    existing = ctx.IO.read_text(file_path)
    if existing is None:
        existing = ""

    if not existing.strip():
        existing = f"# 💼 工作笔记 — {date_str}\n\n---\n"

    new_content = existing.rstrip() + "\n\n" + entry
    ok = ctx.IO.write_text(file_path, new_content)
    if ok:
        _log(f"[discuss] 讨论已归档: {file_path}")
    else:
        _log(f"[discuss] 讨论归档失败: {file_path}")
    return ok


# ============ Skill 热加载注册表 ============
SKILL_REGISTRY = {
    "discuss.start": start,
    "discuss.reply": reply,
    "discuss.conclude": conclude,
    "discuss.cancel": cancel_discuss,
}
