#!/usr/bin/env python3
# 工作1测试：discuss skill 集成验证
import sys; sys.path.insert(0, 'src')

# 测试 1: discuss skill 导入
from skills import idea_discuss
reg = idea_discuss.SKILL_REGISTRY
print(f'✅ discuss skill 注册: {list(reg.keys())}')
assert 'discuss.start' in reg
assert 'discuss.reply' in reg
assert 'discuss.conclude' in reg
assert 'discuss.cancel' in reg

# 测试 2: prompts 注册
import prompts
assert 'discuss.start' in prompts.SKILL_PROMPT_LINES
assert 'discuss.reply' in prompts.SKILL_PROMPT_LINES
assert 'discuss.conclude' in prompts.SKILL_PROMPT_LINES
assert 'discuss.cancel' in prompts.SKILL_PROMPT_LINES
print(f'✅ SKILL_PROMPT_LINES 已注册 discuss skill')

# 测试 3: build_skills_prompt 包含 discuss（始终注入）
all_names = list(prompts.SKILL_PROMPT_LINES.keys())
skills_text = prompts.build_skills_prompt(all_names, injected_rule_tags=[])
assert 'discuss.start' in skills_text
print(f'✅ discuss skill 在 SKILLS prompt 中可见')

# 测试 4: RULES_CORE 包含讨论规则
assert '想法讨论/辩论' in prompts.RULES_CORE
assert 'discuss_pending' in prompts.RULES_CORE
assert 'discuss.reply' in prompts.RULES_CORE
print(f'✅ RULES_CORE 包含讨论规则和优先级')

# 测试 5: brain.py 相关集合包含 discuss
from brain import _SIMPLE_SKILLS
assert 'discuss.start' in _SIMPLE_SKILLS
assert 'discuss.reply' in _SIMPLE_SKILLS
print(f'✅ brain.py _SIMPLE_SKILLS 已包含 discuss')

print(f'\n🎉 工作1全部测试通过')
