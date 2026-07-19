from ..schemas.submission_context import SubmissionContext

def build_context(context: SubmissionContext) -> dict:
    data = context.model_dump()
    result = str(context.execution_result).strip().lower()
    passed = result in {"passed", "pass", "success", "successful", "accepted", "ok"}
    struggle_indicators = []
    if context.hint_count > 0: struggle_indicators.append("used_hints")
    if context.attempt_count > 1: struggle_indicators.append("multiple_attempts")
    if not passed: struggle_indicators.append("execution_not_passed")
    data.update({
        "execution_status": "passed" if passed else "not_passed",
        "execution_passed": passed,
        "struggle_indicators": struggle_indicators,
        "struggle_level": "high" if len(struggle_indicators) >= 2 else "moderate" if struggle_indicators else "low",
        "code_line_count": len(context.code.splitlines()),
        "has_runtime_output": bool(str(context.execution_result).strip()),
    })
    return data
