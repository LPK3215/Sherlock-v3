from yuxi.agents.buildin.chatbot.prompt import PROMPT


def test_chatbot_prompt_keeps_sherlock_as_the_global_identity():
    assert "你是夏洛克(Sherlock)" in PROMPT
    assert "你的身份始终是夏洛克" in PROMPT
    assert "Skill 只是你在当前任务中调用的能力包" in PROMPT
    assert "多个 Skill 可以同时存在" in PROMPT
    assert "你是一个交互式智能体" not in PROMPT
