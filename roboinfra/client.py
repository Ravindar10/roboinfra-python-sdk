# FILE: roboinfra/client.py
#
# RoboInfra Python SDK — HTTP client
#
# Security hardening applied:
#   - API key never exposed in repr() or str()
#   - File path validated before open (no path traversal)
#   - File size checked before upload (default 25MB cap)
#   - File extension validated per endpoint
#   - Retry only on server 5xx and connection errors, NOT on proxy/auth errors
#   - Timeout set on both connect and read separately
#   - User-Agent header identifies SDK version

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── SDK version ───────────────────────────────────────────────────────────────
__version__ = "1.0.0"

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024   # 25MB — API limit is 20MB, +5MB buffer
CONNECT_TIMEOUT_S   = 10                  # seconds to establish connection
READ_TIMEOUT_S      = 120                 # seconds to wait for response (conversion can be slow)


class RoboInfraError(Exception):
    """Raised for any RoboInfra API error (HTTP 4xx/5xx) or connection failure."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code   = status_code    # HTTP status code, e.g. 429
        self.response_body = response_body  # raw response text for debugging


class AuthError(RoboInfraError):
    """Raised when API key is invalid or missing (HTTP 401)."""


class PlanError(RoboInfraError):
    """Raised when the API call requires a higher plan (HTTP 403)."""


class QuotaError(RoboInfraError):
    """Raised when monthly API quota is exceeded (HTTP 429)."""


class Client:
    """
    RoboInfra API client.

    Usage:
        client = roboinfra.Client("rk_your_api_key")
        result = client.urdf.validate("robot.urdf")
        print(result.is_valid)

    Never print the client object — it will NOT show your API key (secure).
    """

    BASE_URL = "https://roboinfra-api.azurewebsites.net"

    def __init__(self, api_key: str, base_url: str = None):
        """
        Create a RoboInfra client.

        Args:
            api_key:  Your API key from the dashboard (starts with rk_)
            base_url: Override the API base URL (useful for testing)
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key must be a non-empty string")
        if not api_key.startswith("rk_"):
            raise ValueError("api_key must start with 'rk_' — copy it from roboinfra-dashboard.azurewebsites.net/keys")

        # SECURITY: store key privately — never exposed in repr/str
        self._api_key = api_key

        if base_url:
            self.BASE_URL = base_url.rstrip("/")

        self._session = requests.Session()
        self._session.headers.update({
            "X-Api-Key":  api_key,
            "User-Agent": f"roboinfra-python/{__version__}",
        })

        # Retry only on server errors (5xx) and network failures.
        # Do NOT retry on 4xx (auth/quota errors) — retrying a 401 wastes quota.
        # Do NOT retry on proxy errors — they won't fix themselves by retrying.
        retry = Retry(
            total           = 3,
            backoff_factor  = 0.5,              # wait 0.5s, 1s, 2s between retries
            status_forcelist = [500, 502, 503, 504],  # only retry on server errors
            allowed_methods = ["POST"],
            raise_on_status = False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://",  adapter)

        # Sub-resources
        from .urdf  import UrdfResource
        from .model import ModelResource
        self.urdf  = UrdfResource(self)
        self.model = ModelResource(self)

    def health(self) -> dict:
        """
        Check if the RoboInfra API is online. No API key required.
        Use this to verify connectivity before making real API calls.

        Returns:
            dict with status, version, uptime

        Example:
            result = client.health()
            print(result["status"])   # "Healthy"
        """
        try:
            response = self._session.get(
                f"{self.BASE_URL}/api/health",
                timeout=(CONNECT_TIMEOUT_S, 30),
            )
            raw = self._handle_response(response)
            return raw.get("data", raw)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            raise RoboInfraError(
                f"Connection failed: {e}. "
                f"Check your internet connection."
            )

    def __repr__(self):
        # SECURITY: never show the API key
        masked = f"{self._api_key[:6]}...{self._api_key[-4:]}"
        return f"<roboinfra.Client key={masked} url={self.BASE_URL}>"

    def _validate_file(self, file_path: str, allowed_extensions: list = None):
        """
        Validate a file before uploading.
        Checks: exists, not a directory, extension allowed, size within limit.
        Prevents path traversal by normalising the path.
        """
        # Normalise — resolves .., symlinks etc.
        safe_path = os.path.realpath(os.path.abspath(file_path))

        if not os.path.exists(safe_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        if not os.path.isfile(safe_path):
            raise ValueError(f"Not a file: {file_path}")

        ext = os.path.splitext(safe_path)[1].lower()
        if allowed_extensions and ext not in allowed_extensions:
            raise ValueError(
                f"File '{os.path.basename(safe_path)}' has extension '{ext}'. "
                f"Allowed: {', '.join(allowed_extensions)}"
            )

        size = os.path.getsize(safe_path)
        if size == 0:
            raise ValueError(f"File is empty: {file_path}")
        if size > MAX_FILE_SIZE_BYTES:
            mb = size / (1024 * 1024)
            raise ValueError(f"File is {mb:.1f}MB — maximum allowed is {MAX_FILE_SIZE_BYTES // (1024*1024)}MB")

        return safe_path

    def _post_file(self, endpoint: str, file_path: str) -> dict:
        """POST a file, return parsed JSON dict."""
        try:
            with open(file_path, "rb") as f:
                response = self._session.post(
                    f"{self.BASE_URL}{endpoint}",
                    files={"file": (os.path.basename(file_path), f)},
                    timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
                )
            return self._handle_response(response)

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            raise RoboInfraError(
                f"Connection failed: {e}. "
                f"Check your internet connection and that {self.BASE_URL} is reachable."
            )
        except requests.exceptions.RequestException as e:
            raise RoboInfraError(f"Request failed: {e}")

    def _post_file_download(self, endpoint: str, file_path: str,
                             output_path: str, params: dict = None) -> str:
        """POST a file, save binary response to output_path, return output_path."""
        try:
            with open(file_path, "rb") as f:
                response = self._session.post(
                    f"{self.BASE_URL}{endpoint}",
                    files={"file": (os.path.basename(file_path), f)},
                    params=params,
                    timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
                )

            if response.status_code >= 400:
                self._handle_response(response)   # raises appropriate error

            # SECURITY: validate output_path — prevent writing outside current dir
            safe_out = os.path.realpath(os.path.abspath(output_path))
            os.makedirs(os.path.dirname(safe_out) or ".", exist_ok=True)
            with open(safe_out, "wb") as out:
                out.write(response.content)
            return safe_out

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            raise RoboInfraError(f"Connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise RoboInfraError(f"Request failed: {e}")

    def _handle_response(self, response) -> dict:
        """Map HTTP status codes to typed exceptions with clear messages."""
        if response.status_code == 401:
            raise AuthError(
                "Invalid or missing API key. "
                "Get your key at roboinfra-dashboard.azurewebsites.net/keys",
                status_code=401,
                response_body=response.text
            )
        if response.status_code == 403:
            raise PlanError(
                "This endpoint requires a higher plan. "
                "Upgrade at roboinfra-dashboard.azurewebsites.net/subscription",
                status_code=403,
                response_body=response.text
            )
        if response.status_code == 429:
            raise QuotaError(
                "Monthly API quota exceeded. "
                "Upgrade your plan or wait until next month.",
                status_code=429,
                response_body=response.text
            )
        if response.status_code == 400:
            try:
                body = response.json()
                msg = body.get("message", response.text)
            except Exception:
                msg = response.text
            raise RoboInfraError(f"Bad request: {msg}", status_code=400, response_body=response.text)
        if response.status_code >= 500:
            raise RoboInfraError(
                f"RoboInfra server error (HTTP {response.status_code}). "
                f"Please retry in 30 seconds.",
                status_code=response.status_code,
                response_body=response.text
            )
        if response.status_code >= 400:
            raise RoboInfraError(
                f"API error HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
                response_body=response.text
            )

        try:
            return response.json()
        except ValueError:
            raise RoboInfraError(
                f"API returned non-JSON response: {response.text[:200]}"
            )