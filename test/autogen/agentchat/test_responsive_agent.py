import pytest
from flaml.autogen.agentchat import ResponsiveAgent


def test_trigger():
    agent = ResponsiveAgent("a0", max_consecutive_auto_reply=0, llm_config=False, human_input_mode="NEVER")
    agent1 = ResponsiveAgent("a1", max_consecutive_auto_reply=0, human_input_mode="NEVER")
    agent.register_auto_reply(agent1, lambda recipient, messages, sender, config: (True, "hello"))
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello"
    agent.register_auto_reply("a1", lambda recipient, messages, sender, config: (True, "hello a1"))
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello a1"
    agent.register_auto_reply(
        ResponsiveAgent, lambda recipient, messages, sender, config: (True, "hello responsive agent")
    )
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello responsive agent"
    agent.register_auto_reply(
        lambda sender: sender.name.startswith("a"), lambda recipient, messages, sender, config: (True, "hello a")
    )
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello a"
    agent.register_auto_reply(
        lambda sender: sender.name.startswith("b"), lambda recipient, messages, sender, config: (True, "hello b")
    )
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello a"
    agent.register_auto_reply(
        ["agent2", agent1], lambda recipient, messages, sender, config: (True, "hello agent2 or agent1")
    )
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello agent2 or agent1"
    agent.register_auto_reply(
        ["agent2", "agent3"], lambda recipient, messages, sender, config: (True, "hello agent2 or agent3")
    )
    agent1.initiate_chat(agent, message="hi")
    assert agent1.last_message(agent)["content"] == "hello agent2 or agent1"
    pytest.raises(ValueError, agent.register_auto_reply, 1, lambda recipient, messages, sender, config: (True, "hi"))
    pytest.raises(ValueError, agent._match_trigger, 1, agent1)


def test_context():
    agent = ResponsiveAgent("a0", max_consecutive_auto_reply=0, llm_config=False, human_input_mode="NEVER")
    agent1 = ResponsiveAgent("a1", max_consecutive_auto_reply=0, human_input_mode="NEVER")
    agent1.send(
        {
            "content": "hello {name}",
            "context": {
                "name": "there",
            },
        },
        agent,
    )
    # expect hello {name} to be printed
    agent1.send(
        {
            "content": lambda context: f"hello {context['name']}",
            "context": {
                "name": "there",
            },
        },
        agent,
    )
    # expect hello there to be printed
    agent.llm_config = {"allow_format_str_template": True}
    agent1.send(
        {
            "content": "hello {name}",
            "context": {
                "name": "there",
            },
        },
        agent,
    )
    # expect hello there to be printed


def test_max_consecutive_auto_reply():
    agent = ResponsiveAgent("a0", max_consecutive_auto_reply=2, llm_config=False, human_input_mode="NEVER")
    agent1 = ResponsiveAgent("a1", max_consecutive_auto_reply=0, human_input_mode="NEVER")
    assert agent.max_consecutive_auto_reply() == agent.max_consecutive_auto_reply(agent1) == 2
    agent.update_max_consecutive_auto_reply(1)
    assert agent.max_consecutive_auto_reply() == agent.max_consecutive_auto_reply(agent1) == 1

    agent1.initiate_chat(agent, message="hello")
    assert agent._consecutive_auto_reply_counter[agent1] == 1
    agent1.initiate_chat(agent, message="hello again")
    # with auto reply because the counter is reset
    assert agent1.last_message(agent)["role"] == "user"
    assert len(agent1.chat_messages[agent]) == 2
    assert len(agent.chat_messages[agent1]) == 2

    assert agent._consecutive_auto_reply_counter[agent1] == 1
    agent1.send(message="bye", recipient=agent)
    # no auto reply
    assert agent1.last_message(agent)["role"] == "assistant"

    agent1.initiate_chat(agent, clear_history=False, message="hi")
    assert len(agent1.chat_messages[agent]) > 2
    assert len(agent.chat_messages[agent1]) > 2

    assert agent1.reply_at_receive[agent] == agent.reply_at_receive[agent1] is True
    agent1.stop_reply_at_receive(agent)
    assert agent1.reply_at_receive[agent] is False and agent.reply_at_receive[agent1] is True


def test_responsive_agent():
    dummy_agent_1 = ResponsiveAgent(name="dummy_agent_1", human_input_mode="ALWAYS")
    dummy_agent_2 = ResponsiveAgent(name="dummy_agent_2", human_input_mode="TERMINATE")

    # monkeypatch.setattr(sys, "stdin", StringIO("exit"))
    dummy_agent_1.receive("hello", dummy_agent_2)  # receive a str
    # monkeypatch.setattr(sys, "stdin", StringIO("TERMINATE\n\n"))
    dummy_agent_1.receive(
        {
            "content": "hello {name}",
            "context": {
                "name": "dummy_agent_2",
            },
        },
        dummy_agent_2,
    )  # receive a dict
    assert "context" in dummy_agent_1.chat_messages[dummy_agent_2][-1]
    # receive dict without openai fields to be printed, such as "content", 'function_call'. There should be no error raised.
    pre_len = len(dummy_agent_1.chat_messages[dummy_agent_2])
    with pytest.raises(ValueError):
        dummy_agent_1.receive({"message": "hello"}, dummy_agent_2)
    assert pre_len == len(
        dummy_agent_1.chat_messages[dummy_agent_2]
    ), "When the message is not an valid openai message, it should not be appended to the oai conversation."

    # monkeypatch.setattr(sys, "stdin", StringIO("exit"))
    dummy_agent_1.send("TERMINATE", dummy_agent_2)  # send a str
    # monkeypatch.setattr(sys, "stdin", StringIO("exit"))
    dummy_agent_1.send(
        {
            "content": "TERMINATE",
        },
        dummy_agent_2,
    )  # send a dict

    # send dict with no openai fields
    pre_len = len(dummy_agent_1.chat_messages[dummy_agent_2])
    with pytest.raises(ValueError):
        dummy_agent_1.send({"message": "hello"}, dummy_agent_2)

    assert pre_len == len(
        dummy_agent_1.chat_messages[dummy_agent_2]
    ), "When the message is not a valid openai message, it should not be appended to the oai conversation."

    # update system message
    dummy_agent_1.update_system_message("new system message")
    assert dummy_agent_1.system_message == "new system message"


def test_long_auto_reply():
    # prepare code and function call
    longcodeblock = [("python", "print('hello world')"), ("python", "print('*' * 5000)")]

    def return_long_out():
        return "*" * 5000

    func_call = {"name": "return_long_out", "arguments": "{}"}

    # create agent with pre-defined token limit
    dummy_agent = ResponsiveAgent(
        name="dummy_agent",
        human_input_mode="ALWAYS",
        function_map={"return_long_out": return_long_out},
        auto_reply_token_limit=50,
        code_execution_config={"use_docker": False},
    )
    long_error = dummy_agent.execute_code_blocks(longcodeblock)
    assert (
        "hello world" in long_error[1]
    ), f"Output from previous code block should be shown in the message. Reuturn: {long_error}"
    assert (
        "Error: The output exceeds the length limit and is truncated." in long_error[1]
    ), "The error message for long reply should be shown in the message."
    assert (
        dummy_agent.execute_function(func_call)[1]["content"]
        == "Error: The return from this call exceeds the token limit."
    ), "The error message for long reply should be shown in the message."

    # create agent with no token limit
    dummy_agent = ResponsiveAgent(
        name="dummy_agent",
        human_input_mode="ALWAYS",
        function_map={"return_long_out": return_long_out},
        code_execution_config={"use_docker": False},
    )
    long_return = dummy_agent.execute_code_blocks(longcodeblock)
    assert "****" in long_return[1], f"The output should be valid. Return: {long_return}"
    assert "****" in dummy_agent.execute_function(func_call)[1]["content"], "The return from this call should be valid."


if __name__ == "__main__":
    # test_trigger()
    # test_context()
    # test_max_consecutive_auto_reply()
    # test_responsive_agent(pytest.monkeypatch)
    test_long_auto_reply()
