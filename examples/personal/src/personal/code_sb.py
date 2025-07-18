import abc
import inspect
import json
import logging
import warnings
from typing import ClassVar, Type, Dict, Any, Tuple
from urllib.parse import urljoin

import httpx
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


def _code_runner(code_to_run: str, max_output_chars: int):
    """
    Executes code and captures output, status, and errors.
    This function is converted to a string and sent to the sandbox.
    """
    import contextlib
    import io
    import json
    import os
    import traceback

    # Suppress warnings and set thread limits inside the runner
    warnings.filterwarnings('ignore')
    os.environ['OPENBLAS_NUM_THREADS'] = '16'

    stdout = io.StringIO()
    stderr = io.StringIO()
    status = "completed"

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            exec(code_to_run)
        except Exception:
            status = "error"
            stderr.write(traceback.format_exc())

    stdout_val = stdout.getvalue()
    stderr_val = stderr.getvalue()

    # Truncate output if it exceeds the max length
    if len(stdout_val) > max_output_chars:
        stdout_val = stdout_val[:max_output_chars] + "<...output truncated...>"
    if len(stderr_val) > max_output_chars:
        stderr_val = stderr_val[:max_output_chars] + "<...output truncated...>"

    output = {"process_status": status,
              "stdout": stdout_val, "stderr": stderr_val}
    print(json.dumps(output))


class Sandbox(abc.ABC):
    """
    Abstract base class for a remote code execution sandbox.

    Args:
        uri: The base URI of the sandbox server.
        timeout: Default request timeout in seconds.
    """

    def __init__(self, *, uri: HttpUrl, timeout: float = 10.0):
        self.url = self._get_execute_url(uri)
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100,
                                max_keepalive_connections=20),
            timeout=timeout,
        )

    async def _send_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends an execution request to the sandbox."""
        try:
            response = await self.http_client.post(
                url=self.url,
                json=request_payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
            return self._parse_request_output(response)
        except httpx.TimeoutException:
            logger.warning("Request timed out.")
            return {"process_status": "timeout", "stdout": "", "stderr": "Request timed out.\n"}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"process_status": "error", "stdout": "", "stderr": f"HTTP Error: {e.response.status_code}\n"}
        except json.JSONDecodeError as e:
            logger.exception("Error parsing output: %s", e)
            return {'process_status': 'error', 'stdout': '', 'stderr': 'Error parsing sandbox output.\n'}

    @abc.abstractmethod
    def _parse_request_output(self, response: httpx.Response) -> Dict[str, Any]:
        pass

    @abc.abstractmethod
    def _get_execute_url(self, uri: HttpUrl) -> str:
        pass

    @abc.abstractmethod
    def _prepare_request(self, code_to_execute: str, timeout: float) -> Dict[str, Any]:
        pass

    async def execute_code(
        self,
        generated_code: str,
        timeout: float = 10.0,
        max_output_characters: int = 1000,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Executes code in the sandbox by sending a self-contained runner script.
        """
        # Clean the input code
        generated_code = generated_code.strip().strip("`")

        # Get the source of the runner function and combine it with the code to run
        runner_source = inspect.getsource(_code_runner)
        code_to_execute = (
            f"{runner_source}\n\n"
            f"_code_runner(code_to_run={repr(generated_code)}, max_output_chars={max_output_characters})"
        )

        request_payload = self._prepare_request(code_to_execute, timeout)
        output = await self._send_request(request_payload)
        return output


class LocalSandbox(Sandbox):
    """Locally hosted sandbox."""

    def _get_execute_url(self, uri: HttpUrl) -> str:
        return urljoin(str(uri), "execute")

    def _parse_request_output(self, response: httpx.Response) -> Dict[str, Any]:
        return response.json()

    def _prepare_request(self, code_to_execute: str, timeout: float, language: str = 'python', **kwargs) -> Dict[str, Any]:
        return {
            "generated_code": code_to_execute,
            "timeout": timeout,
            "language": language,
        }


class PistonSandbox(Sandbox):
    """Piston sandbox (https://github.com/engineer-man/piston)."""

    def _get_execute_url(self, uri: HttpUrl) -> str:
        # Piston's execute endpoint is at the root or /api/v2/execute
        return urljoin(str(uri), "api/v2/execute")

    def _parse_request_output(self, response: httpx.Response) -> Dict[str, Any]:
        output = response.json()
        run_info = output.get('run', {})
        if not run_info or run_info.get('signal') == "SIGKILL":
            return {'process_status': 'error', 'stdout': '', 'stderr': 'Execution killed (SIGKILL), possibly due to timeout or memory limit.'}
        # The actual output is a JSON string inside the 'output' field
        return json.loads(run_info.get('output', '{}'))

    def _prepare_request(self, code_to_execute: str, timeout: float, **kwargs) -> Dict[str, Any]:
        return {
            "language": "python",  # 'py' is an alias, 'python' is standard
            "version": "3.10",  # Specify major.minor
            "files": [{"content": code_to_execute}],
            "run_timeout": int(timeout * 1000),  # Piston expects milliseconds
        }


# Using ClassVar for type hinting the dictionary of classes
sandboxes: ClassVar[Dict[str, Type[Sandbox]]] = {
    'local': LocalSandbox,
    'piston': PistonSandbox,
}


def get_sandbox(sandbox_type: str = "local", **kwargs) -> Sandbox:
    """A factory function to get a sandbox instance by type."""
    sandbox_class = sandboxes.get(sandbox_type.lower())
    if not sandbox_class:
        raise ValueError(
            f"Unknown sandbox type: '{sandbox_type}'. Available types: {list(sandboxes.keys())}")
    return sandbox_class(**kwargs)
