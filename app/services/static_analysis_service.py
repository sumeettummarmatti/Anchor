"""Timeout-bound, non-executing source-code analysis."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.schemas.static_analysis import Diagnostic, StaticAnalysisResult


class StaticAnalysisService:
    """Runs supported linters in a temporary directory and normalizes their output."""

    _python_languages = {"python", "python3", "py"}
    _javascript_languages = {"javascript", "js", "node", "nodejs"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(self, language: str, code: str) -> StaticAnalysisResult:
        normalized = language.lower().strip()
        if normalized in self._python_languages:
            return await self._run_ruff(code)
        if normalized in self._javascript_languages:
            return await self._run_eslint(code)
        return StaticAnalysisResult(
            language=language,
            analyzer="unsupported",
            available=False,
            diagnostics=[],
        )

    async def _run_ruff(self, code: str) -> StaticAnalysisResult:
        with tempfile.TemporaryDirectory(prefix="mentor-analysis-") as directory:
            source = Path(directory) / "submission.py"
            source.write_text(code, encoding="utf-8")
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--output-format=json",
                    str(source),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(
                    process.communicate(), timeout=self.settings.static_analysis_timeout_seconds
                )
            except FileNotFoundError:
                return self._unavailable("ruff")
            except TimeoutError:
                process.kill()
                await process.communicate()
                return self._unavailable("ruff", "Analysis timed out.")

        try:
            raw_diagnostics = json.loads(stdout or b"[]")
        except json.JSONDecodeError:
            return self._unavailable("ruff", "The analyzer returned an invalid response.")
        diagnostics = [
            Diagnostic(
                line=item["location"]["row"],
                column=item["location"]["column"],
                severity="warning",
                code=item["code"],
                message=item["message"],
            )
            for item in raw_diagnostics
        ]
        return StaticAnalysisResult(
            language="python", analyzer="ruff", available=True, diagnostics=diagnostics
        )

    async def _run_eslint(self, code: str) -> StaticAnalysisResult:
        eslint = shutil.which("eslint")
        if not eslint:
            return StaticAnalysisResult(
                language="javascript", analyzer="eslint", available=False, diagnostics=[]
            )
        with tempfile.TemporaryDirectory(prefix="mentor-analysis-") as directory:
            source = Path(directory) / "submission.js"
            source.write_text(code, encoding="utf-8")
            try:
                process = await asyncio.create_subprocess_exec(
                    eslint,
                    "--format=json",
                    str(source),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(
                    process.communicate(), timeout=self.settings.static_analysis_timeout_seconds
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                return StaticAnalysisResult(
                    language="javascript", analyzer="eslint", available=False, diagnostics=[]
                )
        try:
            messages = json.loads(stdout or b"[]")[0].get("messages", [])
        except (IndexError, json.JSONDecodeError):
            return StaticAnalysisResult(
                language="javascript", analyzer="eslint", available=False, diagnostics=[]
            )
        diagnostics = [
            Diagnostic(
                line=item.get("line", 1),
                column=item.get("column", 1),
                severity="error" if item.get("severity") == 2 else "warning",
                code=item.get("ruleId") or "ESLINT",
                message=item["message"],
            )
            for item in messages
        ]
        return StaticAnalysisResult(
            language="javascript", analyzer="eslint", available=True, diagnostics=diagnostics
        )

    @staticmethod
    def _unavailable(analyzer: str, message: str | None = None) -> StaticAnalysisResult:
        diagnostics = (
            [
                Diagnostic(
                    line=1,
                    column=1,
                    severity="info",
                    code="ANALYZER_UNAVAILABLE",
                    message=message,
                )
            ]
            if message
            else []
        )
        return StaticAnalysisResult(
            language="python", analyzer=analyzer, available=False, diagnostics=diagnostics
        )
