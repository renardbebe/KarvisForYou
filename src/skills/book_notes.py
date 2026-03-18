# -*- coding: utf-8 -*-
"""
Skill: book.*
读书笔记系统：创建书籍笔记、添加摘录/感想、AI 总结/金句。
"""
import sys
from datetime import datetime, timezone, timedelta


BEIJING_TZ = timezone(timedelta(hours=8))

# 阅读状态定义：内部 key → (emoji, 中文标签)
_STATUS_MAP = {
    "want_read": ("📋", "想读"),
    "reading":   ("📖", "在读"),
    "finished":  ("✅", "读完"),
    "paused":    ("⏸️", "搁置"),
}
# 反向映射：中文 / emoji / 别名 → 内部 key
_STATUS_ALIAS = {}
for _k, (_e, _cn) in _STATUS_MAP.items():
    _STATUS_ALIAS[_k] = _k
    _STATUS_ALIAS[_cn] = _k
    _STATUS_ALIAS[_e] = _k
# 常见别名补充
_STATUS_ALIAS.update({
    "想看": "want_read", "待读": "want_read", "wish": "want_read",
    "在看": "reading", "开始读": "reading", "开始看": "reading",
    "读完了": "finished", "看完了": "finished", "看完": "finished", "读完": "finished", "done": "finished",
    "暂停": "paused", "搁置": "paused", "放下": "paused",
})


def _normalize_status(raw):
    """将用户输入的各种状态表述统一为内部 key"""
    if not raw:
        return None
    raw = raw.strip().lower()
    return _STATUS_ALIAS.get(raw)


def _status_display(status_key):
    """内部 key → 'emoji 中文'"""
    e, cn = _STATUS_MAP.get(status_key, ("📋", "想读"))
    return f"{e} {cn}"


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _now_str():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")


def _book_file(name, ctx):
    return f"{ctx.book_notes_dir}/{name}.md"


def _book_list_file(ctx):
    return f"{ctx.book_notes_dir}/_书单.md"


def create(params, state, ctx):
    """
    创建或切换书籍笔记。

    params:
        name: str — 书名
        author: str — 作者（LLM 填写）
        category: str — 分类（LLM 填写）
        description: str — 简介（LLM 填写）
        thought: str — 可选，首条感想
        status: str — 可选，阅读状态：want_read(想读)/reading(在读)/finished(读完)/paused(搁置)，默认 want_read
    """
    name = (params.get("name") or "").strip()
    if not name:
        return {"success": False, "reply": "需要书名"}

    author = (params.get("author") or "未知").strip()
    category = (params.get("category") or "未知").strip()
    description = (params.get("description") or "").strip()
    first_thought = (params.get("thought") or "").strip()

    # 解析阅读状态：默认 want_read
    raw_status = (params.get("status") or "").strip()
    status_key = _normalize_status(raw_status) or "want_read"

    file_path = _book_file(name, ctx)

    # 检查是否已存在
    existing = ctx.IO.read_text(file_path)
    if existing is None:
        return {"success": False, "reply": "读取失败"}

    if not existing.strip():
        # 创建新笔记
        today = datetime.now(BEIJING_TZ).strftime('%Y-%m-%d')
        date_label = "开始阅读" if status_key == "reading" else "加入书单"
        template = f"""---
type: book
title: {name}
author: {author}
category: {category}
start_date: {today}
status: {status_key}
tags: [读书, {category}]
---

# 📚 {name}

## 📋 基本信息

- **作者**：{author}
- **分类**：{category}
- **简介**：{description or '暂无'}
- **{date_label}**：{today}

---

## ✂️ 摘录

---

## 💡 我的思考

---

## 💎 可分享的金句

---

## 🤖 AI 总结

---
"""
        if first_thought:
            template = template.replace(
                "## 💡 我的思考\n\n---",
                f"## 💡 我的思考\n\n{first_thought}\n*— {_now_str()}*\n\n---"
            )

        ok = ctx.IO.write_text(file_path, template)
        if not ok:
            return {"success": False, "reply": "创建笔记失败"}

        # 更新书单索引
        _update_book_list(name, author, category, status_key, ctx)
        _log(f"[book.create] 新建: {name} (状态: {status_key})")
    else:
        _log(f"[book.create] 切换到已有: {name}")
        # 文件已存在 + 有感想 → 自动转调 book.thought
        if first_thought:
            _log(f"[book.create] 已有笔记且携带感想，转调 book.thought")
            thought_result = thought({"content": first_thought, "book": name}, state, ctx)
            thought_result.setdefault("state_updates", {})["active_book"] = name
            return thought_result

    # 更新 state 中的活跃书籍
    return {
        "success": True,
        "state_updates": {"active_book": name}
    }


def excerpt(params, state, ctx):
    """
    添加书摘。

    params:
        content: str — 摘录内容
        book: str — 可选，指定书名（默认用 active_book）
    """
    content = (params.get("content") or "").strip()
    if not content:
        return {"success": False, "reply": "摘录内容不能为空"}

    book = (params.get("book") or state.get("active_book", "")).strip()
    if not book:
        return {"success": False, "reply": "还没有在读的书，先说一下书名吧"}

    entry = f"> {content}\n*— {_now_str()}*\n"
    ok = ctx.IO.append_to_section(_book_file(book, ctx), "## ✂️ 摘录", entry)

    if ok:
        _log(f"[book.excerpt] 添加到 {book}")
        return {"success": True}
    else:
        return {"success": False, "reply": f"写入《{book}》失败"}


def thought(params, state, ctx):
    """
    添加读书感想。

    params:
        content: str — 感想内容
        book: str — 可选，指定书名
    """
    content = (params.get("content") or "").strip()
    if not content:
        return {"success": False, "reply": "感想不能为空"}

    book = (params.get("book") or state.get("active_book", "")).strip()
    if not book:
        return {"success": False, "reply": "还没有在读的书，先说一下书名吧"}

    entry = f"{content}\n*— {_now_str()}*\n"
    ok = ctx.IO.append_to_section(_book_file(book, ctx), "## 💡 我的思考", entry)

    if ok:
        _log(f"[book.thought] 添加到 {book}")
        return {"success": True}
    else:
        return {"success": False, "reply": f"写入《{book}》失败"}


def summary(params, state, ctx):
    """
    AI 生成读书总结。

    params:
        book: str — 可选，指定书名
    """
    book = (params.get("book") or state.get("active_book", "")).strip()
    if not book:
        return {"success": False, "reply": "需要指定书名"}

    content = ctx.IO.read_text(_book_file(book, ctx))
    if not content or not content.strip():
        return {"success": False, "reply": f"没找到《{book}》的笔记"}

    from brain import call_deepseek
    import json
    import prompts

    prompt = prompts.get("BOOK_SUMMARY_USER", book=book, content=content[:3000])

    response = call_deepseek([
        {"role": "system", "content": prompts.BOOK_SUMMARY_SYSTEM},
        {"role": "user", "content": prompt}
    ], max_tokens=800, temperature=0.7)

    if not response:
        return {"success": False, "reply": "AI 分析失败"}

    # 解析 + 写入
    analysis = _parse_json(response)
    if not analysis:
        return {"success": False, "reply": "AI 分析结果解析失败"}

    summary_md = f"""### 📖 核心观点
{analysis.get('core_ideas', '')}

### 🧠 思考脉络
{analysis.get('thinking_path', '')}

### 📚 关联阅读
{analysis.get('recommendations', '')}

### 💬 一句话总结
{analysis.get('one_liner', '')}

*🤖 AI 生成于 {_now_str()}*
"""
    ok = ctx.IO.append_to_section(_book_file(book, ctx), "## 🤖 AI 总结", summary_md)

    if ok:
        one_liner = analysis.get("one_liner", "总结已生成")
        return {"success": True, "reply": f"《{book}》总结已生成\n💬 {one_liner}"}
    else:
        return {"success": False, "reply": "写入总结失败"}


def quotes(params, state, ctx):
    """
    AI 从摘录中提炼金句。

    params:
        book: str — 可选，指定书名
    """
    book = (params.get("book") or state.get("active_book", "")).strip()
    if not book:
        return {"success": False, "reply": "需要指定书名"}

    content = ctx.IO.read_text(_book_file(book, ctx))
    if not content or not content.strip():
        return {"success": False, "reply": f"没找到《{book}》的笔记"}

    from brain import call_deepseek
    import json
    import prompts

    prompt = prompts.get("BOOK_QUOTES_USER", book=book, content=content[:3000])

    response = call_deepseek([
        {"role": "system", "content": prompts.BOOK_QUOTES_SYSTEM},
        {"role": "user", "content": prompt}
    ], max_tokens=500, temperature=0.8)

    if not response:
        return {"success": False, "reply": "AI 提炼失败"}

    quotes_list = _parse_json(response)
    if not isinstance(quotes_list, list):
        return {"success": False, "reply": "金句提炼结果解析失败"}

    # 写入笔记
    quotes_md = "\n".join([f"- {q}" for q in quotes_list])
    quotes_md += f"\n\n*🤖 AI 提炼于 {_now_str()}*\n"
    ctx.IO.append_to_section(_book_file(book, ctx), "## 💎 可分享的金句", quotes_md)

    # 直接在回复中展示（方便复制）
    reply_lines = [f"《{book}》金句:"]
    for i, q in enumerate(quotes_list, 1):
        reply_lines.append(f"{i}. {q}")
    return {"success": True, "reply": "\n".join(reply_lines)}


def list_books(params, state, ctx):
    """
    查看书单。

    直接读取 _书单.md 返回内容，按状态分组展示。
    params:
        status: str — 可选，过滤状态（want_read/reading/finished/paused）
    """
    content = ctx.IO.read_text(_book_list_file(ctx)) or ""
    if not content.strip():
        return {"success": True, "reply": "还没有书单记录哦~ 你可以说「记录我想看的书：xxx」来开始~"}

    # 按状态过滤
    filter_status = _normalize_status(params.get("status") or "") if params.get("status") else None

    # 解析表格行，提取书籍信息
    lines = content.strip().split("\n")
    grouped = {}  # status_key → list of book info strings
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        if "书名" in line or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 4:
            name = cells[0].replace("[[", "").replace("]]", "")
            author = cells[1] if len(cells) > 1 else ""
            category = cells[2] if len(cells) > 2 else ""
            status_raw = cells[3] if len(cells) > 3 else ""
            # 解析表格中的状态 emoji+中文 → 内部 key
            sk = _normalize_status(status_raw.replace(" ", "")) or "want_read"
            # 尝试去掉 emoji 后再匹配
            if not _normalize_status(status_raw.replace(" ", "")):
                for _e, _cn in _STATUS_MAP.values():
                    cleaned = status_raw.replace(_e, "").strip()
                    sk2 = _normalize_status(cleaned)
                    if sk2:
                        sk = sk2
                        break

            if filter_status and sk != filter_status:
                continue

            grouped.setdefault(sk, []).append(f"  · 《{name}》{author} [{category}]")

    if not grouped:
        if filter_status:
            e, cn = _STATUS_MAP.get(filter_status, ("", ""))
            return {"success": True, "reply": f"没有「{cn}」状态的书~"}
        return {"success": True, "reply": "书单是空的~ 你可以说「记录我想看的书：xxx」来开始~"}

    # 按状态顺序输出
    order = ["reading", "want_read", "paused", "finished"]
    parts = []
    total = 0
    for sk in order:
        books = grouped.get(sk)
        if not books:
            continue
        total += len(books)
        e, cn = _STATUS_MAP.get(sk, ("📋", "未知"))
        parts.append(f"{e} {cn}（{len(books)}本）:\n" + "\n".join(books))

    reply = f"📚 你的书单（共 {total} 本）:\n\n" + "\n\n".join(parts)
    return {"success": True, "reply": reply}


def update_status(params, state, ctx):
    """
    修改书籍阅读状态。

    params:
        book: str — 书名
        status: str — 新状态：want_read(想读)/reading(在读)/finished(读完)/paused(搁置)
    """
    book = (params.get("book") or state.get("active_book", "")).strip()
    if not book:
        return {"success": False, "reply": "需要指定书名"}

    raw_status = (params.get("status") or "").strip()
    new_key = _normalize_status(raw_status)
    if not new_key:
        return {"success": False, "reply": f"不认识的状态「{raw_status}」，支持：想读 / 在读 / 读完 / 搁置"}

    # 1. 更新书籍笔记 frontmatter 中的 status
    file_path = _book_file(book, ctx)
    note_content = ctx.IO.read_text(file_path) or ""
    if not note_content.strip():
        return {"success": False, "reply": f"没找到《{book}》的笔记"}

    import re
    updated = False
    if re.search(r'^status:\s*\S+', note_content, re.MULTILINE):
        note_content = re.sub(
            r'^(status:\s*)\S+',
            f'\\g<1>{new_key}',
            note_content,
            count=1,
            flags=re.MULTILINE
        )
        updated = True

    # 如果状态变为 reading，更新"开始阅读"日期；变为 finished，添加"读完"日期
    today = datetime.now(BEIJING_TZ).strftime('%Y-%m-%d')
    if new_key == "reading" and "**开始阅读**" not in note_content and "**加入书单**" in note_content:
        note_content = note_content.replace(
            "**加入书单**",
            "**开始阅读**"
        )
    if new_key == "finished" and "**读完日期**" not in note_content:
        note_content = note_content.replace(
            "\n---\n\n## ✂️ 摘录",
            f"\n- **读完日期**：{today}\n\n---\n\n## ✂️ 摘录"
        )

    if updated:
        ctx.IO.write_text(file_path, note_content)

    # 2. 更新 _书单.md 中对应行的状态列
    _update_book_list_status(book, new_key, ctx)

    display = _status_display(new_key)
    _log(f"[book.status] {book} → {new_key}")
    return {"success": True, "reply": f"《{book}》状态已更新为「{display}」"}


def _update_book_list(name, author, category, status_key, ctx):
    """更新书单索引"""
    existing = ctx.IO.read_text(_book_list_file(ctx)) or ""
    if not existing.strip():
        existing = "# 📚 书单\n\n| 书名 | 作者 | 分类 | 状态 | 日期 |\n|------|------|------|------|------|\n"

    date = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    display = _status_display(status_key)
    new_row = f"| [[{name}]] | {author} | {category} | {display} | {date} |"
    new_content = existing.rstrip() + "\n" + new_row + "\n"
    ctx.IO.write_text(_book_list_file(ctx), new_content)


def _update_book_list_status(book_name, new_status_key, ctx):
    """更新 _书单.md 中某本书的状态列"""
    content = ctx.IO.read_text(_book_list_file(ctx)) or ""
    if not content.strip():
        return

    lines = content.split("\n")
    updated = False
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        # 跳过表头和分隔行
        if "书名" in line or "---" in line:
            continue
        # 检查是否匹配书名
        if f"[[{book_name}]]" in line or book_name in line:
            cells = line.split("|")
            if len(cells) >= 6:  # | 书名 | 作者 | 分类 | 状态 | 日期 |  → 6 个 |
                cells[4] = f" {_status_display(new_status_key)} "
                lines[i] = "|".join(cells)
                updated = True
                break

    if updated:
        ctx.IO.write_text(_book_list_file(ctx), "\n".join(lines))


def _parse_json(text):
    """容错 JSON 解析"""
    import json
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{") if "{" in text else text.find("[")
        end = max(text.rfind("}"), text.rfind("]"))
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
    return None


# Skill 热加载注册表（O-010）
SKILL_REGISTRY = {
    "book.create": create,
    "book.excerpt": excerpt,
    "book.thought": thought,
    "book.summary": summary,
    "book.quotes": quotes,
    "book.list": list_books,
    "book.status": update_status,
}
