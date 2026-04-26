# FILE: roboinfra/urdf.py
#
# BUG FIX: body.get("data", {}) → body.get("data") or {}
#
# EXACT ROOT CAUSE (confirmed by testing against the live API):
#
#   The API returns this JSON for an invalid URDF (HTTP 400):
#     {
#       "success": false,
#       "statusCode": 400,
#       "message": "Root element must be <robot> | URDF must contain at least one <link> element.",
#       "data": null,        <-- data is null, NOT { "isValid": false, "errors": [...] }
#       "errors": null
#     }
#
#   The old code used:
#     data = body.get("data", {})
#
#   Python's dict.get(key, default) only uses the default when the KEY IS ABSENT.
#   When the key EXISTS with a null value, it returns None, not the default.
#   So data = None (not {}).
#
#   Then:
#     if "isValid" in data or "errors" in data:
#   raises: TypeError: argument of type 'NoneType' is not iterable
#
#   That TypeError was caught by:
#     except (_json.JSONDecodeError, Exception): pass
#   which fell through to: raise  → re-raises the original RoboInfraError
#
#   So the 400 handling never worked. The SDK always raised RoboInfraError
#   for invalid URDFs, even in the "fixed" version.
#
# THE FIX:
#   data = body.get("data") or {}
#   This works because: None or {} = {}
#   Even if data key is absent OR null, data is always a dict.
#
# AFTER THIS FIX:
#   client.urdf.validate("bad.urdf")
#   → returns ValidationResult(is_valid=False, errors=["Root element must be <robot>", ...])
#   → never raises RoboInfraError for invalid URDFs
#
# ALSO PUBLISH TO PYPI after this fix so pip install roboinfra-sdk gets it.

from .models import ValidationResult, AnalysisResult

URDF_MAX_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB


class UrdfResource:
    """
    URDF validation and kinematic analysis.

    Access via:
        client = roboinfra.Client("rk_xxx")
        client.urdf.validate("robot.urdf")
        client.urdf.analyze("robot.urdf")
    """

    def __init__(self, client):
        self._client = client

    def validate(self, file_path: str) -> "ValidationResult":
        """
        Validate a URDF file against 9 structural checks.
        Available on ALL plans (Free, Basic, Pro).

        Args:
            file_path: Path to your .urdf file. Max 1MB.

        Returns:
            ValidationResult:
              .is_valid  bool  — True if all 9 checks pass
              .errors    list  — error strings if invalid, empty if valid

        Raises:
            FileNotFoundError  if file does not exist
            ValueError         if file is wrong extension or too large
            AuthError          if API key is invalid (HTTP 401)
            QuotaError         if monthly quota exceeded (HTTP 429)
            RoboInfraError     for server errors (HTTP 5xx) only

        NOTE: An invalid URDF (HTTP 400) returns ValidationResult(is_valid=False).
              It does NOT raise an exception.
        """
        import os
        import json as _json
        from .client import RoboInfraError

        safe_path = self._client._validate_file(
            file_path, allowed_extensions=[".urdf", ".xacro"]
        )

        size = os.path.getsize(safe_path)
        if size > URDF_MAX_SIZE_BYTES:
            raise ValueError(
                f"URDF file is {size / 1024:.0f}KB — maximum allowed is 1MB."
            )

        try:
            raw = self._client._post_file("/api/urdf/validate", safe_path)
            # HTTP 200 path: raw = { "data": { "isValid": true, "errors": [] } }
            data = (raw.get("data") or {})
            return ValidationResult(data)

        except RoboInfraError as e:
            if e.status_code == 400 and e.response_body:
                try:
                    body = _json.loads(e.response_body)

                    # ── THE FIX ───────────────────────────────────────────────
                    # body.get("data") returns None when data is null in JSON.
                    # "or {}" converts None to {} so the next lines never fail.
                    # WRONG: body.get("data", {}) → returns None when key=null
                    # RIGHT: body.get("data") or {}  → always returns a dict
                    data = body.get("data") or {}

                    is_valid = data.get("isValid", False)

                    # Prefer data.errors list; fall back to splitting message
                    errors = data.get("errors") or []
                    if not errors and not is_valid:
                        msg = body.get("message", "")
                        errors = [p.strip() for p in msg.split("|") if p.strip()]

                    return ValidationResult({"isValid": is_valid, "errors": errors})

                except (_json.JSONDecodeError, Exception):
                    pass  # Body unparseable — fall through to re-raise

            # Re-raise for 401, 403, 429, 5xx, or truly unexpected 400
            raise

    def analyze(self, file_path: str) -> "AnalysisResult":
        """
        Kinematic analysis — DOF, joint chain, end effectors.
        Requires Basic or Pro plan.

        Args:
            file_path: Path to your .urdf file. Max 1MB.

        Returns:
            AnalysisResult with robot_name, link_count, joint_count,
            dof, max_chain_depth, root_link, end_effectors, joints.

        Raises:
            PlanError   if plan is Free (requires Basic+)
            AuthError   if API key is invalid
            QuotaError  if monthly quota exceeded
        """
        safe_path = self._client._validate_file(
            file_path, allowed_extensions=[".urdf", ".xacro"]
        )
        raw = self._client._post_file("/api/urdf/analyze", safe_path)
        data = (raw.get("data") or {})
        return AnalysisResult(data)