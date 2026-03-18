# -*- coding: utf-8 -*-
"""
Skill: mood.generate
每天自动从当天消息中提取情绪，生成情绪日记。
写入 02-Notes/情感日记/{date}.md（追加 AI 情绪分析段）。

数据源（纯对话推断，不依赖打卡）：
1. Quick-Notes + 归档笔记（全天消息）— 主要数据源
2. 决策日志的 skill/thinking 字段（辅助意图判断）
3. 近期对话上下文（state.recent_messages）
"""
import sys
import json
from datetime import datetime, timezone, timedelta


BEIJING_TZ = timezone(timedelta(hours=8))


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def execute(params, state, ctx):
    """
    生成当日情绪日记。

    params:
        date: str — 可选，YYYY-MM-DD，默认今天
    """
    date_str = (params.get("date") or "").strip()
    if not date_str:
        date_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    _log(f"[mood.generate] 开始生成 {date_str} 情绪日记")

    # 1. 收集当天所有对话数据
    data = _collect_mood_data(date_str, state, ctx)

    if not data["notes"].strip():
        _log("[mood.generate] 今天没有记录")
        return {"success": True, "reply": f"今天（{date_str}）还没有记录，无法生成情绪日记"}

    # 2. AI 从对话中推断情绪
    from brain import call_deepseek
    analysis = _ai_analyze_mood(data, date_str, call_deepseek, state)

    if not analysis:
        return {"success": False, "reply": "AI 情绪分析失败"}

    # 所有评分都来自 AI 对话推断
    analysis["score_source"] = "conversation"

    # 3. 写入 state.mood_scores
    mood_entry = {
        "date": date_str,
        "score": analysis.get("mood_score", 5),
        "source": "conversation",
        "label": analysis.get("mood_label", "")
    }
    scores = state.setdefault("mood_scores", [])
    # 去重：同一天只保留最新
    scores = [s for s in scores if s.get("date") != date_str]
    scores.append(mood_entry)
    state["mood_scores"] = scores

    # 4. 构建 Markdown 并写入
    mood_md = _build_mood_diary(date_str, analysis, data)
    file_path = f"{ctx.emotion_notes_dir}/{date_str}.md"
    ok = _write_mood_diary(ctx, file_path, date_str, mood_md)

    if ok:
        _log(f"[mood.generate] 情绪日记已写入: {file_path}")
        emoji = analysis.get("mood_emoji", "📝")
        label = analysis.get("mood_label", "")
        score = analysis.get("mood_score", "?")
        return {
            "success": True,
            "reply": f"情绪日记已生成 {emoji}\n{label}（{score}/10）"
        }
    else:
        return {"success": False, "reply": "情绪日记写入失败"}


def _collect_mood_data(date_str, state, ctx):
    """并发收集当天所有对话/笔记数据（不依赖打卡）"""
    from concurrent.futures import ThreadPoolExecutor

    files_to_read = {
        "quick_notes": ctx.quick_notes_file,
        "emotion": f"{ctx.emotion_notes_dir}/{date_str}.md",
        "fun": f"{ctx.fun_notes_dir}/{date_str}.md",
        "work": f"{ctx.work_notes_dir}/{date_str}.md",
        "misc": ctx.misc_file,
        "decisions": ctx.decision_log_file,
    }

    results = {}
    try:
        from brain import _executor
        futures = {k: _executor.submit(ctx.IO.read_text, v) for k, v in files_to_read.items()}
    except ImportError:
        _pool = ThreadPoolExecutor(max_workers=6)
        futures = {k: _pool.submit(ctx.IO.read_text, v) for k, v in files_to_read.items()}

    for k, fut in futures.items():
        try:
            results[k] = fut.result(timeout=30) or ""
        except Exception:
            results[k] = ""

    # 提取当天 Quick-Notes 条目
    qn_entries = _extract_date_entries(results["quick_notes"], date_str)

    # 提取当天碎碎念
    misc_entries = _extract_date_entries(results["misc"], date_str)

    # 提取当天决策日志
    decision_entries = _extract_decision_entries(results["decisions"], date_str)

    # 组装笔记文本
    parts = []
    if qn_entries:
        parts.extend(["【快速笔记】", qn_entries])
    for key, label in [("emotion", "情感日记"), ("fun", "生活趣事"), ("work", "工作笔记")]:
        content = results[key].strip()
        if content:
            parts.extend([f"【{label}】", content])
    if misc_entries:
        parts.extend(["【碎碎念】", misc_entries])

    # 近期对话（state 中的 recent_messages）
    recent = state.get("recent_messages", [])
    today_msgs = [m for m in recent if m.get("text", "").strip()]
    if today_msgs:
        conv_parts = []
        for m in today_msgs[-20:]:
            role = "用户" if m.get("role") == "user" else "Karvis"
            conv_parts.append(f"[{role}] {m.get('text', '')[:100]}")
        parts.extend(["【近期对话】", "\n".join(conv_parts)])

    notes = "\n\n".join(parts)

    return {
        "notes": notes,
        "decisions": decision_entries,
    }


def _extract_date_entries(text, date_str):
    """从 Markdown 文件中提取指定日期的条目"""
    if not text:
        return ""
    entries = []
    sections = text.split("\n## ")
    for section in sections[1:]:
        first_line = section.split("\n")[0].strip()
        if first_line.startswith(date_str):
            entries.append("## " + section.strip())
    return "\n\n".join(entries)


def _extract_decision_entries(text, date_str):
    """从 JSONL 决策日志中提取当天条目"""
    if not text:
        return []
    entries = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            ts = entry.get("ts", "")
            if ts.startswith(date_str):
                entries.append(entry)
        except Exception:
            pass
    return entries



def _ai_analyze_mood(data, date_str, call_deepseek, state=None):
    """调用 AI 从当天对话内容中推断情绪"""
    import prompts

    state = state or {}

    # 组装 prompt
    parts = [f"分析以下 {date_str} 的对话记录，从中推断用户全天的情绪变化。"]

    if data["notes"]:
        parts.append(f"\n【当天对话和笔记记录】\n{data['notes'][:3000]}")

    if data["decisions"]:
        parts.append("\n【AI 决策日志（辅助）】")
        for d in data["decisions"][:10]:
            parts.append(f"- {d.get('ts','')} skill={d.get('skill','')} thinking={d.get('thinking','')}")

    parts.append(prompts.MOOD_JSON_FORMAT)

    prompt = "\n".join(parts)

    response = call_deepseek([
        {"role": "system", "content": prompts.MOOD_SYSTEM},
        {"role": "user", "content": prompt}
    ], max_tokens=800, temperature=0.7)

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
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
    _log(f"[mood.generate] AI 分析 JSON 解析失败: {text[:200]}")
    return None


def _build_mood_diary(date_str, analysis, data):
    """构建情绪日记 Markdown"""
    emoji = analysis.get("mood_emoji", "📝")
    label = analysis.get("mood_label", "")
    score = analysis.get("mood_score", "?")
    trend = analysis.get("trend", "")
    moments = analysis.get("key_moments", [])
    insight = analysis.get("insight", "")

    lines = [
        f"## {emoji} 情绪分析",
        "",
        f"**整体评分**：{score}/10（对话推断）",
        f"**情绪标签**：{label}",
        "",
    ]

    if trend:
        lines.extend([f"**情绪走势**：{trend}", ""])

    if moments:
        lines.append("**关键情绪节点**：")
        for m in moments:
            t = m.get("time", "")
            e = m.get("emoji", "•")
            event = m.get("event", "")
            mood = m.get("mood", "")
            lines.append(f"- {t} {e} {event}（{mood}）")
        lines.append("")

    if insight:
        lines.extend(["**AI 洞察**：", "", insight, ""])

    now_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    lines.extend([
        "---",
        "",
        f"*🤖 情绪分析自动生成于 {now_str}（基于对话内容推断）*",
    ])

    return "\n".join(lines)


def _write_mood_diary(ctx, file_path, date_str, mood_content):
    """写入情绪日记（追加到已有归档内容之后，替换已有分析段）"""
    existing = ctx.IO.read_text(file_path)
    if existing is None:
        existing = ""

    # 获取星期几
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekdays[dt.weekday()]
    except Exception:
        weekday = ""

    if not existing.strip():
        # 全新文件
        header = f"---\ndate: {date_str}\ntype: 情感日记\ntags: [情感日记]\n---\n\n"
        header += f"# 💭 情感日记 · {date_str} {weekday}\n\n"
        new_content = header + mood_content
    elif "## " in existing and "情绪分析" in existing:
        # 替换已有的情绪分析段
        # 找到 "## xxx 情绪分析" 的位置
        import re
        pattern = r'\n## .{0,5} 情绪分析'
        match = re.search(pattern, existing)
        if match:
            before = existing[:match.start()]
            new_content = before.rstrip() + "\n\n" + mood_content
        else:
            new_content = existing.rstrip() + "\n\n" + mood_content
    else:
        # 追加到已有归档内容之后
        new_content = existing.rstrip() + "\n\n" + mood_content

    return ctx.IO.write_text(file_path, new_content)


# Skill 热加载注册表
SKILL_REGISTRY = {
    "mood.generate": execute,
}
