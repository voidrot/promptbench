from promptbench.config.schema import PromptBenchConfig
from promptbench.runtime_logging import preview_payload, should_log


def test_should_log_levels() -> None:
    cfg = PromptBenchConfig()
    cfg.policies.log_verbosity = "debug"
    assert should_log(cfg, "normal") is True
    assert should_log(cfg, "debug") is True
    assert should_log(cfg, "trace") is False


def test_preview_payload_truncates() -> None:
    s = "x" * 2000
    out = preview_payload(s, max_chars=50)
    assert out.endswith("...<truncated>")
    assert len(out) < len(s)
