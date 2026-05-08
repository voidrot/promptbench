from promptbench.provider.model_ids import parse_model_id


def test_parse_model_id() -> None:
    provider, model = parse_model_id("openai/gpt-4.1-mini")
    assert provider == "openai"
    assert model == "gpt-4.1-mini"
