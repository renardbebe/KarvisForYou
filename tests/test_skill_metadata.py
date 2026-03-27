# -*- coding: utf-8 -*-
"""
KarvisForYou Skill 元数据一致性验证测试（V13 重构验证）

验证目标：
1. 所有 SKILL_REGISTRY 条目均升级为新格式（包含 prompt/simple/skip_note）
2. skill_loader 自动生成的 prompt_lines / simple_skills / skip_note_skills 与原硬编码一致
3. prompts.py 的 build_skills_prompt 正常工作
4. 不存在缺失 prompt 的 skill（除 ignore 外）
5. 无死代码残留（_decorator.py 已删除）

运行方式:
    cd KarvisForYou/src && python -m pytest ../tests/test_skill_metadata.py -v
    或:
    cd KarvisForYou && python tests/test_skill_metadata.py
"""
import os
import sys

# 让 import 能找到 src/
_src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
sys.path.insert(0, _src_dir)

# 清除 skill_loader 缓存，确保从头加载
import skill_loader
skill_loader._cached_registry = None
skill_loader._cached_metadata = None

# ============================================================
# 测试工具
# ============================================================

_pass_count = 0
_fail_count = 0


def _assert(condition, msg=""):
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        print(f"  ✓ {msg}")
    else:
        _fail_count += 1
        print(f"  ✗ FAIL: {msg}")


def _section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# 原硬编码值（重构前的参照基准）
# ============================================================

# 原 brain.py 中的 _SIMPLE_SKILLS（重构前 + settings.skills 优化为 simple）
ORIGINAL_SIMPLE_SKILLS = frozenset({
    "note.save", "classify.archive",
    "todo.add", "todo.done", "todo.edit", "todo.delete", "todo.list", "todo.remind_cancel",
    "book.create", "book.excerpt", "book.thought", "book.summary", "book.quotes", "book.list", "book.status",
    "media.create", "media.thought",
    "mood.generate", "voice.journal",
    "settings.nickname", "settings.ai_name", "settings.soul", "settings.info", "settings.skills",
    "web.token",
    "habit.propose", "habit.nudge", "habit.status", "habit.complete",
    "decision.record", "dynamic",
    "reflect.push", "reflect.answer", "reflect.skip", "reflect.history",
    "discuss.start", "discuss.reply", "discuss.conclude", "discuss.cancel",
})

# 原 brain.py 中的 _SKIP_NOTE_SKILLS（重构前 + settings.skills 优化为 skip_note）
ORIGINAL_SKIP_NOTE_SKILLS = frozenset({
    "todo.add", "todo.done", "todo.edit", "todo.delete", "todo.list",
    "habit.propose", "habit.nudge", "habit.status", "habit.complete",
    "decision.record", "decision.review", "decision.list",
    "book.create", "book.excerpt", "book.thought", "book.summary", "book.quotes", "book.list", "book.status",
    "media.create", "media.thought",
    "web.token", "weather.query", "web.search",
    "settings.nickname", "settings.ai_name", "settings.soul", "settings.info", "settings.frequency", "settings.skills",
    "deep.dive",
})

# 原 prompts.py 中的 SKILL_PROMPT_LINES 键集合（重构前）
ORIGINAL_PROMPT_KEYS = frozenset({
    "note.save", "classify.archive",
    "todo.add", "todo.done", "todo.edit", "todo.delete", "todo.remind_cancel", "todo.list",
    "weather.query", "web.search",
    "daily.generate", "weekly.review", "mood.generate",
    "book.create", "book.excerpt", "book.thought", "book.summary", "book.quotes", "book.list", "book.status",
    "media.create", "media.thought",
    "habit.propose", "habit.nudge", "habit.status", "habit.complete",
    "decision.record", "decision.review", "decision.list",
    "discuss.start", "discuss.reply", "discuss.conclude", "discuss.cancel",
    "voice.journal", "deep.dive",
    "internal.read", "internal.search", "internal.list",
    "settings.nickname", "settings.ai_name", "settings.soul", "settings.info", "settings.skills", "settings.frequency",
    "web.token", "dynamic",
    "reflect.push", "reflect.answer", "reflect.skip", "reflect.history",
    "ignore",
    "finance.query", "finance.snapshot", "finance.import", "finance.monthly",
})


# ============================================================
# 测试 1: _decorator.py 已删除
# ============================================================

def test_decorator_deleted():
    _section("测试 1: _decorator.py 死代码已删除")

    decorator_path = os.path.join(_src_dir, "skills", "_decorator.py")
    _assert(not os.path.exists(decorator_path),
            "_decorator.py 已删除")


# ============================================================
# 测试 2: Skill 加载正常
# ============================================================

def test_skill_loading():
    _section("测试 2: Skill 加载正常")

    registry = skill_loader.load_skill_registry()
    metadata = skill_loader.get_skill_metadata()

    _assert(len(registry) > 40, f"加载了 {len(registry)} 个 skill（预期 >40）")
    _assert(len(metadata) == len(registry),
            f"metadata 数量与 registry 一致 ({len(metadata)})")

    # 每个 registry entry 都有对应的 handler
    for name, handler in registry.items():
        _assert(callable(handler), f"skill '{name}' handler 可调用")


# ============================================================
# 测试 3: 所有 skill 均声明了 prompt 字段
# ============================================================

def test_all_skills_have_prompt():
    _section("测试 3: 所有 skill 均声明了 prompt 字段")

    metadata = skill_loader.get_skill_metadata()
    missing_prompt = []

    for name, meta in metadata.items():
        if "prompt" not in meta:
            missing_prompt.append(name)

    _assert(len(missing_prompt) == 0,
            f"所有 skill 都有 prompt 字段 (缺失: {missing_prompt})")


# ============================================================
# 测试 4: simple_skills 与原硬编码一致
# ============================================================

def test_simple_skills_consistency():
    _section("测试 4: simple_skills 与原硬编码一致")

    new_simple = skill_loader.get_simple_skills()

    # 原来有但新版没有的
    missing = ORIGINAL_SIMPLE_SKILLS - new_simple
    # 新版有但原来没有的
    extra = new_simple - ORIGINAL_SIMPLE_SKILLS

    _assert(len(missing) == 0,
            f"没有遗漏的 simple skill (遗漏: {missing})")
    _assert(len(extra) == 0,
            f"没有多余的 simple skill (多余: {extra})")
    _assert(new_simple == ORIGINAL_SIMPLE_SKILLS,
            f"simple_skills 完全一致 ({len(new_simple)} 个)")


# ============================================================
# 测试 5: skip_note_skills 与原硬编码一致
# ============================================================

def test_skip_note_skills_consistency():
    _section("测试 5: skip_note_skills 与原硬编码一致")

    new_skip = skill_loader.get_skip_note_skills()

    missing = ORIGINAL_SKIP_NOTE_SKILLS - new_skip
    extra = new_skip - ORIGINAL_SKIP_NOTE_SKILLS

    _assert(len(missing) == 0,
            f"没有遗漏的 skip_note skill (遗漏: {missing})")
    _assert(len(extra) == 0,
            f"没有多余的 skip_note skill (多余: {extra})")
    _assert(new_skip == ORIGINAL_SKIP_NOTE_SKILLS,
            f"skip_note_skills 完全一致 ({len(new_skip)} 个)")


# ============================================================
# 测试 6: prompt_lines 键集合与原硬编码一致
# ============================================================

def test_prompt_lines_consistency():
    _section("测试 6: prompt_lines 键集合与原硬编码一致")

    new_prompt_lines = skill_loader.get_prompt_lines()
    new_keys = frozenset(new_prompt_lines.keys())

    missing = ORIGINAL_PROMPT_KEYS - new_keys
    extra = new_keys - ORIGINAL_PROMPT_KEYS

    _assert(len(missing) == 0,
            f"没有遗漏的 prompt 键 (遗漏: {missing})")

    # monthly.review 是新增的（原来的 SKILL_PROMPT_LINES 没有，因为月报是后加的）
    unexpected_extra = extra - {"monthly.review"}
    _assert(len(unexpected_extra) == 0,
            f"没有意外多余的 prompt 键 (多余: {unexpected_extra})")

    # 验证每个 prompt 描述不为空
    for name, desc in new_prompt_lines.items():
        _assert(len(desc) > 10,
                f"skill '{name}' 的 prompt 描述有实质内容 ({len(desc)} 字符)")


# ============================================================
# 测试 7: build_skills_prompt 正常工作
# ============================================================

def test_build_skills_prompt():
    _section("测试 7: build_skills_prompt 正常工作")

    import prompts

    # 全量生成
    all_names = list(skill_loader.get_prompt_lines().keys())
    result = prompts.build_skills_prompt(all_names)

    _assert(result.startswith("# 可用 Skill"), "全量 prompt 以标题开头")
    _assert("note.save" in result, "全量 prompt 包含 note.save")
    _assert("todo.add" in result, "全量 prompt 包含 todo.add")
    _assert("ignore" in result, "全量 prompt 包含 ignore")

    # 条件注入：不传 books_media 标签时，book.* 不出现
    result_filtered = prompts.build_skills_prompt(
        all_names,
        injected_rule_tags=["habits"]  # 只注入 habits，不含 books_media
    )
    _assert("book.create" not in result_filtered,
            "条件过滤后不包含 book.create")
    _assert("habit.propose" in result_filtered,
            "条件过滤后包含 habit.propose")
    _assert("todo.add" in result_filtered,
            "条件过滤后仍包含核心 skill todo.add")

    # 空列表
    result_empty = prompts.build_skills_prompt([])
    _assert(result_empty == "", "空列表返回空字符串")

    # 部分列表
    result_partial = prompts.build_skills_prompt(["todo.add", "todo.done"])
    _assert("todo.add" in result_partial, "部分列表包含 todo.add")
    _assert("note.save" not in result_partial, "部分列表不包含 note.save")


# ============================================================
# 测试 8: visibility 字段正确设置
# ============================================================

def test_visibility():
    _section("测试 8: visibility 字段正确")

    metadata = skill_loader.get_skill_metadata()

    private_skills = {name for name, meta in metadata.items()
                      if meta.get("visibility") == "private"}

    expected_private = {"finance.query", "finance.snapshot", "finance.import", "finance.monthly"}
    _assert(private_skills == expected_private,
            f"private skills 正确: {private_skills}")


# ============================================================
# 测试 9: 无循环导入
# ============================================================

def test_no_circular_import():
    _section("测试 9: 无循环导入")

    # 重新导入 prompts（触发延迟加载）
    try:
        import importlib
        import prompts
        importlib.reload(prompts)

        # 触发延迟加载
        prompts._ensure_prompt_lines()
        result = prompts.build_skills_prompt(["todo.add"])

        _assert("todo.add" in result, "prompts 模块无循环导入，正常工作")
    except ImportError as e:
        _assert(False, f"存在循环导入: {e}")


# ============================================================
# 测试 10: 元数据完整性 — 每个 SKILL_REGISTRY 条目均为新格式
# ============================================================

def test_all_new_format():
    _section("测试 10: 所有 SKILL_REGISTRY 条目均为新格式")

    metadata = skill_loader.get_skill_metadata()
    old_format = []

    for name, meta in metadata.items():
        # 新格式至少有 prompt 字段；旧格式只有 visibility
        if "prompt" not in meta and name != "ignore":
            old_format.append(name)

    _assert(len(old_format) == 0,
            f"没有残留旧格式的 skill (残留: {old_format})")


# ============================================================
# 运行所有测试
# ============================================================

def main():
    global _pass_count, _fail_count

    print(f"\nKarvisForYou Skill 元数据一致性验证测试 (V13)")
    print(f"src 目录: {_src_dir}")

    test_decorator_deleted()
    test_skill_loading()
    test_all_skills_have_prompt()
    test_simple_skills_consistency()
    test_skip_note_skills_consistency()
    test_prompt_lines_consistency()
    test_build_skills_prompt()
    test_visibility()
    test_no_circular_import()
    test_all_new_format()

    # 汇总
    _section("测试结果汇总")
    total = _pass_count + _fail_count
    print(f"  通过: {_pass_count}/{total}")
    print(f"  失败: {_fail_count}/{total}")

    if _fail_count > 0:
        print(f"\n  ✗ 存在失败的测试！")
        sys.exit(1)
    else:
        print(f"\n  ✓ 全部通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
