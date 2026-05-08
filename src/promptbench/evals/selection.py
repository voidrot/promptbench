from __future__ import annotations

import random

from promptbench.config.schema import EvalPrompt, EvalTest


def select_prompt(test: EvalTest) -> tuple[str | None, str]:
    if test.prompt:
        return None, test.prompt

    if not test.prompts:
        return None, ""

    selected = random.choice(test.prompts)
    if isinstance(selected, str):
        return None, selected
    if isinstance(selected, EvalPrompt):
        return selected.id, selected.text

    return None, str(selected)
