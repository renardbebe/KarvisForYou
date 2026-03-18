#!/usr/bin/env python3
"""解决 prompts.py 的 3 处 git merge 冲突"""
import re

with open("src/prompts.py", "r", encoding="utf-8") as f:
    content = f.read()

# === 冲突1: SKILL_PROMPT_LINES (todo.done/edit/delete) ===
# 合并: 服务器的 todo.done(带 all?) + 我们的 todo.edit + todo.delete, 删除 checkin
# 先删掉 checkin 4 行（在冲突上方）
content = re.sub(
    r'    "checkin\.answer".*?\n'
    r'    "checkin\.skip".*?\n'
    r'    "checkin\.cancel".*?\n'
    r'    "checkin\.start".*?\n',
    '', content
)

# 解决冲突1: 保留两边的精华
content = content.replace(
    '<<<<<<< Updated upstream\n'
    """    "todo.done": '**todo.done** `{keyword?, indices?}` — 完成待办。keyword=模糊匹配（如"猫粮"匹配"买猫粮"）；indices=序号完成，支持 "3"/"2-7"/"1,3,5"。有 indices 时优先用 indices。序号对应 todo.list 返回的编号。',\n"""
    """    "todo.edit": '**todo.edit** `{keyword?, index?, new_content?, new_due_date?, new_remind_at?, new_recur?, new_recur_spec?}` — 修改待办。keyword 或 index(1-based序号) 定位要改的条目；new_* 字段指定要修改的属性，传 "" 表示清除该属性。',\n"""
    """    "todo.delete": '**todo.delete** `{keyword?, indices?}` — 删除（废弃）待办，不记入已完成。用于用户说"不做了/删掉/取消这个待办"的场景。keyword=模糊匹配；indices=序号批量删除。注意区分：用户说"做完了"→todo.done，"不做了/删掉"→todo.delete。',\n"""
    '=======\n'
    """    "todo.done": '**todo.done** `{keyword?, indices?, all?}` — 完成待办。keyword=模糊匹配（如"猫粮"匹配"买猫粮"）；indices=序号完成，支持 "3"/"2-7"/"1,3,5"；all=true 全部完成（一次性待办标记完成，循环待办打卡）。有 indices 时优先用 indices。序号对应 todo.list 返回的编号。',\n"""
    '>>>>>>> Stashed changes',
    # 合并结果: 服务器的 todo.done(带all) + 我们的 edit/delete
    """    "todo.done": '**todo.done** `{keyword?, indices?, all?}` — 完成待办。keyword=模糊匹配（如"猫粮"匹配"买猫粮"）；indices=序号完成，支持 "3"/"2-7"/"1,3,5"；all=true 全部完成（一次性待办标记完成，循环待办打卡）。有 indices 时优先用 indices。序号对应 todo.list 返回的编号。',\n"""
    """    "todo.edit": '**todo.edit** `{keyword?, index?, new_content?, new_due_date?, new_remind_at?, new_recur?, new_recur_spec?}` — 修改待办。keyword 或 index(1-based序号) 定位要改的条目；new_* 字段指定要修改的属性，传 "" 表示清除该属性。',\n"""
    """    "todo.delete": '**todo.delete** `{keyword?, indices?}` — 删除（废弃）待办，不记入已完成。用于用户说"不做了/删掉/取消这个待办"的场景。keyword=模糊匹配；indices=序号批量删除。注意区分：用户说"做完了"→todo.done，"不做了/删掉"→todo.delete。',"""
)

# === 冲突2: RULES_CORE 待办管理段 ===
# 策略: 采用服务器版本(更完善的结构化)，同时删除残留的 checkin 引用
# 找到冲突2 并用服务器版本替换
conflict2_start = content.find('<<<<<<< Updated upstream\n- "提醒我')
if conflict2_start == -1:
    # 尝试另一个起点
    conflict2_start = content.find("<<<<<<< Updated upstream\n- \"提醒我")
if conflict2_start >= 0:
    conflict2_end = content.find('>>>>>>> Stashed changes', conflict2_start)
    conflict2_end = content.index('\n', conflict2_end) + 1
    
    # 提取服务器版本 (=======到>>>>>>>之间)
    eq_pos = content.find('=======\n', conflict2_start)
    server_content = content[eq_pos + len('=======\n'):content.find('>>>>>>> Stashed changes', conflict2_start)]
    
    # 删除服务器版本中可能残留的 checkin 引用
    server_content = server_content.replace('- 如果同时 checkin_pending=true，打卡优先\n', '')
    
    content = content[:conflict2_start] + server_content + content[conflict2_end:]
    print("✅ 冲突2已解决: 采用服务器版本的待办管理段")
else:
    print("⚠️ 未找到冲突2")

# === 冲突3: OUTPUT_FORMAT 示例段 ===
# 策略: 保留我们的 todo 时间示例 + 服务器的 thinking 说明
conflict3_start = content.find('<<<<<<< Updated upstream\n示例：用户说"今天提醒我早睡')
if conflict3_start == -1:
    conflict3_start = content.find("<<<<<<< Updated upstream\n示例：用户说")
if conflict3_start >= 0:
    conflict3_end = content.find('>>>>>>> Stashed changes', conflict3_start)
    conflict3_end = content.index('\n', conflict3_end) + 1
    
    # 提取两个版本
    eq_pos = content.find('=======\n', conflict3_start)
    ours = content[conflict3_start + len('<<<<<<< Updated upstream\n'):eq_pos]
    theirs = content[eq_pos + len('=======\n'):content.find('>>>>>>> Stashed changes', conflict3_start)]
    
    # 合并: 我们的示例 + 服务器的 thinking 说明
    merged = ours + '\n' + theirs
    content = content[:conflict3_start] + merged + content[conflict3_end:]
    print("✅ 冲突3已解决: 合并 todo 时间示例 + thinking 说明")
else:
    print("⚠️ 未找到冲突3")

# 也删除反射段中残留的 checkin_pending 引用
content = content.replace('- 如果同时 checkin_pending=true，打卡优先\n', '')

# 确认没有冲突标记残留
assert '<<<<<<<' not in content, "还有未解决的冲突!"
assert '>>>>>>>' not in content, "还有未解决的冲突!"
print(f"✅ 确认无冲突标记残留")

with open("src/prompts.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ prompts.py 冲突全部解决")
