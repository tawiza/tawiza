"""Tests for Code Execution DTOs - pydantic model validation.

This module tests the code execution DTOs including:
- ExecutionBackend and CodeLanguage StrEnums
- CodeExecutionRequest with timeout bounds validation
- ExecutionResult value object
- CodeExecutionResponse with nested results
- PackageInstallRequest
- BackendStatusResponse
- InteractiveCodeRequest / InteractiveCodeResponse with nested execution result
"""

import pytest
from pydantic import ValidationError

from src.application.dtos.code_execution_dtos import (
    BackendStatusResponse,
    CodeExecutionRequest,
    CodeExecutionResponse,
    CodeLanguage,
    ExecutionBackend,
    ExecutionResult,
    InteractiveCodeRequest,
    InteractiveCodeResponse,
    PackageInstallRequest,
)


class TestExecutionBackend:
    """Tests for ExecutionBackend StrEnum."""

    def test_execution_backend_values(self):
        """ExecutionBackend should have correct string values."""
        assert ExecutionBackend.E2B_CLOUD.value == "e2b_cloud"
        assert ExecutionBackend.OPEN_INTERPRETER.value == "open_interpreter"
        assert ExecutionBackend.AUTO.value == "auto"

    def test_execution_backend_is_str(self):
        """ExecutionBackend is a StrEnum so members compare equal to str."""
        assert ExecutionBackend.E2B_CLOUD == "e2b_cloud"
        assert isinstance(ExecutionBackend.AUTO, str)

    def test_execution_backend_from_value(self):
        """ExecutionBackend should be constructible from its value."""
        assert ExecutionBackend("auto") is ExecutionBackend.AUTO
        assert ExecutionBackend("e2b_cloud") is ExecutionBackend.E2B_CLOUD

    def test_execution_backend_invalid_value(self):
        """ExecutionBackend should reject unknown values."""
        with pytest.raises(ValueError):
            ExecutionBackend("does_not_exist")

    def test_execution_backend_members(self):
        """ExecutionBackend should expose exactly three members."""
        assert {b.value for b in ExecutionBackend} == {
            "e2b_cloud",
            "open_interpreter",
            "auto",
        }


class TestCodeLanguage:
    """Tests for CodeLanguage StrEnum."""

    def test_code_language_values(self):
        """CodeLanguage should have correct string values."""
        assert CodeLanguage.PYTHON.value == "python"
        assert CodeLanguage.JAVASCRIPT.value == "javascript"
        assert CodeLanguage.BASH.value == "bash"

    def test_code_language_is_str(self):
        """CodeLanguage is a StrEnum so members compare equal to str."""
        assert CodeLanguage.PYTHON == "python"
        assert isinstance(CodeLanguage.BASH, str)

    def test_code_language_from_value(self):
        """CodeLanguage should be constructible from its value."""
        assert CodeLanguage("python") is CodeLanguage.PYTHON
        assert CodeLanguage("javascript") is CodeLanguage.JAVASCRIPT

    def test_code_language_invalid_value(self):
        """CodeLanguage should reject unknown values."""
        with pytest.raises(ValueError):
            CodeLanguage("ruby")

    def test_code_language_members(self):
        """CodeLanguage should expose exactly three members."""
        assert {lang.value for lang in CodeLanguage} == {
            "python",
            "javascript",
            "bash",
        }


class TestCodeExecutionRequest:
    """Tests for CodeExecutionRequest."""

    def test_minimal_construction(self):
        """Only code is required; everything else has defaults."""
        req = CodeExecutionRequest(code="print('hi')")

        assert req.code == "print('hi')"
        assert req.language == CodeLanguage.PYTHON
        assert req.backend is None
        assert req.timeout == 300
        assert req.require_cloud is False
        assert req.require_local is False
        assert req.session_id is None

    def test_code_is_required(self):
        """CodeExecutionRequest should reject missing code."""
        with pytest.raises(ValidationError):
            CodeExecutionRequest()

    def test_full_construction(self):
        """All fields should be settable."""
        req = CodeExecutionRequest(
            code="console.log('x')",
            language=CodeLanguage.JAVASCRIPT,
            backend=ExecutionBackend.E2B_CLOUD,
            timeout=120,
            require_cloud=True,
            require_local=False,
            session_id="sess-1",
        )

        assert req.code == "console.log('x')"
        assert req.language == CodeLanguage.JAVASCRIPT
        assert req.backend == ExecutionBackend.E2B_CLOUD
        assert req.timeout == 120
        assert req.require_cloud is True
        assert req.session_id == "sess-1"

    def test_language_coerced_from_string(self):
        """A raw string should be coerced into the CodeLanguage enum."""
        req = CodeExecutionRequest(code="echo hi", language="bash")
        assert req.language == CodeLanguage.BASH

    def test_backend_coerced_from_string(self):
        """A raw string should be coerced into the ExecutionBackend enum."""
        req = CodeExecutionRequest(code="x", backend="open_interpreter")
        assert req.backend == ExecutionBackend.OPEN_INTERPRETER

    def test_invalid_language_rejected(self):
        """An unknown language string should be rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionRequest(code="x", language="cobol")

    def test_invalid_backend_rejected(self):
        """An unknown backend string should be rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionRequest(code="x", backend="mainframe")

    def test_timeout_lower_bound_ok(self):
        """timeout=1 is the inclusive lower bound and should be accepted."""
        req = CodeExecutionRequest(code="x", timeout=1)
        assert req.timeout == 1

    def test_timeout_upper_bound_ok(self):
        """timeout=600 is the inclusive upper bound and should be accepted."""
        req = CodeExecutionRequest(code="x", timeout=600)
        assert req.timeout == 600

    def test_timeout_below_lower_bound_rejected(self):
        """timeout=0 is below the ge=1 bound and should be rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionRequest(code="x", timeout=0)

    def test_timeout_negative_rejected(self):
        """A negative timeout should be rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionRequest(code="x", timeout=-5)

    def test_timeout_above_upper_bound_rejected(self):
        """timeout=601 exceeds the le=600 bound and should be rejected."""
        with pytest.raises(ValidationError):
            CodeExecutionRequest(code="x", timeout=601)

    def test_timeout_can_be_none(self):
        """timeout is Optional and accepts None explicitly."""
        req = CodeExecutionRequest(code="x", timeout=None)
        assert req.timeout is None

    def test_empty_code_allowed(self):
        """An empty code string is structurally valid (no min length)."""
        req = CodeExecutionRequest(code="")
        assert req.code == ""

    def test_round_trip_serialization(self):
        """model_dump / model_validate should round-trip."""
        req = CodeExecutionRequest(
            code="print(1)",
            language=CodeLanguage.PYTHON,
            backend=ExecutionBackend.AUTO,
            timeout=60,
        )
        dumped = req.model_dump()
        assert dumped["code"] == "print(1)"
        assert dumped["timeout"] == 60

        rebuilt = CodeExecutionRequest.model_validate(dumped)
        assert rebuilt == req

    def test_json_serialization(self):
        """model_dump_json should produce valid JSON re-parseable by the model."""
        req = CodeExecutionRequest(code="print(1)", backend=ExecutionBackend.E2B_CLOUD)
        as_json = req.model_dump_json()
        rebuilt = CodeExecutionRequest.model_validate_json(as_json)
        assert rebuilt.backend == ExecutionBackend.E2B_CLOUD


class TestExecutionResult:
    """Tests for ExecutionResult value object."""

    def test_minimal_construction(self):
        """Only type is required; the rest default to None."""
        result = ExecutionResult(type="text")

        assert result.type == "text"
        assert result.content is None
        assert result.format is None
        assert result.data is None

    def test_type_is_required(self):
        """ExecutionResult should reject missing type."""
        with pytest.raises(ValidationError):
            ExecutionResult()

    def test_full_construction(self):
        """All fields should be settable."""
        result = ExecutionResult(
            type="image",
            content=None,
            format="png",
            data="base64data==",
        )
        assert result.type == "image"
        assert result.format == "png"
        assert result.data == "base64data=="

    def test_text_content(self):
        """A text result should carry its content."""
        result = ExecutionResult(type="text", content="hello world")
        assert result.content == "hello world"

    def test_equality(self):
        """Two ExecutionResults with the same fields should be equal."""
        a = ExecutionResult(type="json", content="{}")
        b = ExecutionResult(type="json", content="{}")
        assert a == b

    def test_inequality(self):
        """ExecutionResults with different fields should not be equal."""
        a = ExecutionResult(type="json", content="{}")
        b = ExecutionResult(type="json", content="[]")
        assert a != b

    def test_round_trip_serialization(self):
        """model_dump / model_validate should round-trip."""
        result = ExecutionResult(type="html", content="<p>x</p>")
        dumped = result.model_dump()
        assert dumped == {
            "type": "html",
            "content": "<p>x</p>",
            "format": None,
            "data": None,
        }
        rebuilt = ExecutionResult.model_validate(dumped)
        assert rebuilt == result


class TestCodeExecutionResponse:
    """Tests for CodeExecutionResponse."""

    def test_minimal_construction(self):
        """Required fields: success, output, execution_time, backend."""
        resp = CodeExecutionResponse(
            success=True,
            output="ok\n",
            execution_time=0.5,
            backend="e2b_cloud",
        )

        assert resp.success is True
        assert resp.output == "ok\n"
        assert resp.execution_time == 0.5
        assert resp.backend == "e2b_cloud"
        assert resp.error is None
        assert resp.stderr is None
        assert resp.results == []
        assert resp.sandbox_id is None
        assert resp.return_code is None

    def test_results_default_is_independent(self):
        """The default results list must not be shared between instances."""
        r1 = CodeExecutionResponse(
            success=True, output="", execution_time=0.1, backend="auto"
        )
        r2 = CodeExecutionResponse(
            success=True, output="", execution_time=0.1, backend="auto"
        )
        r1.results.append(ExecutionResult(type="text", content="x"))
        assert r2.results == []

    @pytest.mark.parametrize("missing", ["success", "output", "execution_time", "backend"])
    def test_required_fields_enforced(self, missing):
        """Each required field must be present."""
        kwargs = {
            "success": True,
            "output": "ok",
            "execution_time": 0.1,
            "backend": "auto",
        }
        del kwargs[missing]
        with pytest.raises(ValidationError):
            CodeExecutionResponse(**kwargs)

    def test_failure_response(self):
        """A failure response should carry error and stderr."""
        resp = CodeExecutionResponse(
            success=False,
            output="",
            error="SyntaxError",
            stderr="Traceback...",
            execution_time=0.01,
            backend="open_interpreter",
            return_code=1,
        )
        assert resp.success is False
        assert resp.error == "SyntaxError"
        assert resp.stderr == "Traceback..."
        assert resp.return_code == 1

    def test_with_nested_results(self):
        """results should accept a list of ExecutionResult."""
        results = [
            ExecutionResult(type="text", content="hello"),
            ExecutionResult(type="image", format="png", data="abc"),
        ]
        resp = CodeExecutionResponse(
            success=True,
            output="hello",
            results=results,
            execution_time=1.0,
            backend="e2b_cloud",
        )
        assert len(resp.results) == 2
        assert resp.results[1].format == "png"

    def test_results_coerced_from_dicts(self):
        """results provided as dicts should be coerced into ExecutionResult."""
        resp = CodeExecutionResponse(
            success=True,
            output="x",
            results=[{"type": "json", "content": "{}"}],
            execution_time=0.1,
            backend="auto",
        )
        assert isinstance(resp.results[0], ExecutionResult)
        assert resp.results[0].type == "json"

    def test_execution_time_accepts_int(self):
        """execution_time is a float but int should coerce."""
        resp = CodeExecutionResponse(
            success=True, output="x", execution_time=2, backend="auto"
        )
        assert resp.execution_time == 2.0
        assert isinstance(resp.execution_time, float)

    def test_round_trip_serialization(self):
        """model_dump / model_validate should round-trip with nested results."""
        resp = CodeExecutionResponse(
            success=True,
            output="out",
            results=[ExecutionResult(type="text", content="t")],
            execution_time=0.25,
            backend="e2b_cloud",
            sandbox_id="sb-1",
        )
        dumped = resp.model_dump()
        assert dumped["sandbox_id"] == "sb-1"
        assert dumped["results"][0]["content"] == "t"

        rebuilt = CodeExecutionResponse.model_validate(dumped)
        assert rebuilt == resp


class TestPackageInstallRequest:
    """Tests for PackageInstallRequest."""

    def test_minimal_construction(self):
        """Only packages is required; language defaults to python."""
        req = PackageInstallRequest(packages=["numpy"])

        assert req.packages == ["numpy"]
        assert req.language == CodeLanguage.PYTHON
        assert req.backend is None

    def test_packages_is_required(self):
        """PackageInstallRequest should reject missing packages."""
        with pytest.raises(ValidationError):
            PackageInstallRequest()

    def test_empty_packages_list_allowed(self):
        """An empty packages list is structurally valid."""
        req = PackageInstallRequest(packages=[])
        assert req.packages == []

    def test_full_construction(self):
        """All fields should be settable."""
        req = PackageInstallRequest(
            packages=["numpy", "pandas"],
            language=CodeLanguage.JAVASCRIPT,
            backend=ExecutionBackend.E2B_CLOUD,
        )
        assert req.packages == ["numpy", "pandas"]
        assert req.language == CodeLanguage.JAVASCRIPT
        assert req.backend == ExecutionBackend.E2B_CLOUD

    def test_invalid_packages_type_rejected(self):
        """packages must be a list of strings, not a bare string-incompatible type."""
        with pytest.raises(ValidationError):
            PackageInstallRequest(packages=[object()])

    def test_round_trip_serialization(self):
        """model_dump / model_validate should round-trip."""
        req = PackageInstallRequest(packages=["requests"], backend=ExecutionBackend.AUTO)
        dumped = req.model_dump()
        rebuilt = PackageInstallRequest.model_validate(dumped)
        assert rebuilt == req


class TestBackendStatusResponse:
    """Tests for BackendStatusResponse."""

    def test_construction(self):
        """All four fields are required."""
        resp = BackendStatusResponse(
            e2b_cloud={"available": True, "adapter": "E2BCodeAdapter"},
            open_interpreter={"available": False},
            default_backend="auto",
            prefer_cloud=True,
        )

        assert resp.e2b_cloud["available"] is True
        assert resp.open_interpreter["available"] is False
        assert resp.default_backend == "auto"
        assert resp.prefer_cloud is True

    @pytest.mark.parametrize(
        "missing", ["e2b_cloud", "open_interpreter", "default_backend", "prefer_cloud"]
    )
    def test_required_fields_enforced(self, missing):
        """Each field is required."""
        kwargs = {
            "e2b_cloud": {},
            "open_interpreter": {},
            "default_backend": "auto",
            "prefer_cloud": False,
        }
        del kwargs[missing]
        with pytest.raises(ValidationError):
            BackendStatusResponse(**kwargs)

    def test_dict_fields_accept_arbitrary_values(self):
        """The status dicts accept arbitrary Any values."""
        resp = BackendStatusResponse(
            e2b_cloud={"nested": {"deep": [1, 2, 3]}},
            open_interpreter={"count": 5},
            default_backend="e2b_cloud",
            prefer_cloud=False,
        )
        assert resp.e2b_cloud["nested"]["deep"] == [1, 2, 3]

    def test_round_trip_serialization(self):
        """model_dump / model_validate should round-trip."""
        resp = BackendStatusResponse(
            e2b_cloud={"available": True},
            open_interpreter={"available": True},
            default_backend="auto",
            prefer_cloud=True,
        )
        dumped = resp.model_dump()
        rebuilt = BackendStatusResponse.model_validate(dumped)
        assert rebuilt == resp


class TestInteractiveCodeRequest:
    """Tests for InteractiveCodeRequest."""

    def test_minimal_construction(self):
        """Only prompt is required; defaults fill the rest."""
        req = InteractiveCodeRequest(prompt="make a fib function")

        assert req.prompt == "make a fib function"
        assert req.language == CodeLanguage.PYTHON
        assert req.model == "qwen2.5-coder:14b"
        assert req.auto_execute is False
        assert req.backend is None

    def test_prompt_is_required(self):
        """InteractiveCodeRequest should reject missing prompt."""
        with pytest.raises(ValidationError):
            InteractiveCodeRequest()

    def test_full_construction(self):
        """All fields should be settable."""
        req = InteractiveCodeRequest(
            prompt="sort a list",
            language=CodeLanguage.JAVASCRIPT,
            model="custom-model",
            auto_execute=True,
            backend=ExecutionBackend.OPEN_INTERPRETER,
        )
        assert req.language == CodeLanguage.JAVASCRIPT
        assert req.model == "custom-model"
        assert req.auto_execute is True
        assert req.backend == ExecutionBackend.OPEN_INTERPRETER

    def test_round_trip_serialization(self):
        """model_dump / model_validate should round-trip."""
        req = InteractiveCodeRequest(prompt="x", auto_execute=True)
        dumped = req.model_dump()
        rebuilt = InteractiveCodeRequest.model_validate(dumped)
        assert rebuilt == req


class TestInteractiveCodeResponse:
    """Tests for InteractiveCodeResponse."""

    def test_minimal_construction(self):
        """generated_code and model_used are required."""
        resp = InteractiveCodeResponse(
            generated_code="def f(): pass",
            model_used="qwen2.5-coder:14b",
        )

        assert resp.generated_code == "def f(): pass"
        assert resp.model_used == "qwen2.5-coder:14b"
        assert resp.explanation is None
        assert resp.execution_result is None

    @pytest.mark.parametrize("missing", ["generated_code", "model_used"])
    def test_required_fields_enforced(self, missing):
        """Each required field must be present."""
        kwargs = {"generated_code": "x", "model_used": "m"}
        del kwargs[missing]
        with pytest.raises(ValidationError):
            InteractiveCodeResponse(**kwargs)

    def test_with_explanation(self):
        """explanation should be settable."""
        resp = InteractiveCodeResponse(
            generated_code="x = 1",
            explanation="Assigns one.",
            model_used="m",
        )
        assert resp.explanation == "Assigns one."

    def test_with_nested_execution_result(self):
        """execution_result should accept a CodeExecutionResponse."""
        exec_result = CodeExecutionResponse(
            success=True,
            output="done",
            execution_time=0.1,
            backend="e2b_cloud",
        )
        resp = InteractiveCodeResponse(
            generated_code="print('done')",
            execution_result=exec_result,
            model_used="m",
        )
        assert resp.execution_result is not None
        assert resp.execution_result.output == "done"

    def test_execution_result_coerced_from_dict(self):
        """A dict execution_result should be coerced into CodeExecutionResponse."""
        resp = InteractiveCodeResponse(
            generated_code="x",
            execution_result={
                "success": True,
                "output": "o",
                "execution_time": 0.2,
                "backend": "auto",
            },
            model_used="m",
        )
        assert isinstance(resp.execution_result, CodeExecutionResponse)
        assert resp.execution_result.backend == "auto"

    def test_round_trip_serialization_with_nested(self):
        """model_dump / model_validate should round-trip with the nested response."""
        exec_result = CodeExecutionResponse(
            success=True,
            output="done",
            execution_time=0.1,
            backend="e2b_cloud",
        )
        resp = InteractiveCodeResponse(
            generated_code="print('done')",
            explanation="prints done",
            execution_result=exec_result,
            model_used="m",
        )
        dumped = resp.model_dump()
        assert dumped["execution_result"]["output"] == "done"

        rebuilt = InteractiveCodeResponse.model_validate(dumped)
        assert rebuilt == resp
