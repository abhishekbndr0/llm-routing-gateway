import pytest
from translate import to_anthropic, to_openai


def test_system_prompt_becomes_top_level():
    out = to_anthropic({"messages": [{"role": "system", "content": "Be brief."},
                                     {"role": "user", "content": "Hi"}]})
    assert out["system"] == "Be brief."
    assert out["messages"] == [{"role": "user", "content": "Hi"}]


def test_max_tokens_default_and_passthrough():
    msgs = [{"role": "user", "content": "Hi"}]
    assert to_anthropic({"messages": msgs})["max_tokens"] == 1024
    assert to_anthropic({"messages": msgs, "max_tokens": 50})["max_tokens"] == 50


def test_consecutive_roles_are_merged():
    out = to_anthropic({"messages": [{"role": "user", "content": "a"},
                                     {"role": "user", "content": "b"}]})
    assert len(out["messages"]) == 1


def test_temperature_clamped():
    out = to_anthropic({"messages": [{"role": "user", "content": "Hi"}], "temperature": 1.5})
    assert out["temperature"] == 1.0


def test_must_start_with_user():
    with pytest.raises(ValueError):
        to_anthropic({"messages": [{"role": "assistant", "content": "Hi"}]})


def test_stop_string_becomes_one_item_list():
    out = to_anthropic({"messages": [{"role": "user", "content": "Hi"}], "stop": "END"})
    assert out["stop_sequences"] == ["END"]


def test_list_content_is_flattened_to_string():
    out = to_anthropic({"messages": [{"role": "user",
                                      "content": [{"type": "text", "text": "hi"}]}]})
    assert out["messages"][0]["content"] == "hi"


def test_to_openai_total_tokens_is_input_plus_output():
    resp = to_openai("hello", "claude-haiku-5-5", input_tokens=12, output_tokens=30)
    assert resp["usage"]["prompt_tokens"] == 12
    assert resp["usage"]["completion_tokens"] == 30
    assert resp["usage"]["total_tokens"] == 42
