# FILE: roboinfra/urdf.py
#
# BUG FIX: validate() now handles HTTP 400 as a ValidationResult(is_valid=False)
#
# ROOT CAUSE:
#   The API returns HTTP 400 when a URDF fails structural checks.
#   Response body contains:
#     { "success": false, "data": { "isValid": false, "errors": [...] } }
#
#   client._handle_response() treated ALL 400 responses as errors and raised:
#     RoboInfraError("Bad request: Root element must be <robot> | ...")
#
#   This was wrong for /api/urdf/validate  a 400 here is a validation RESULT,
#   not an API error. The fix: catch the RoboInfraError(status_code=400) in
#   validate(), parse the response body, and return ValidationResult(is_valid=False).
#
# BEFORE (broken):
#   client.urdf.validate("bad.urdf")
#   → raises RoboInfraError("Bad request: Root element must be <robot>")
#   → any caller (action, user code) crashes even if they just wanted to check validity
#
# AFTER (correct):
#   client.urdf.validate("bad.urdf")
#   → returns ValidationResult(is_valid=False, errors=["Root element must be <robot>", ...])
#   → caller can do: if not result.is_valid: print(result.errors)
#
# WHY only validate() gets this treatment, not analyze():
#   For /api/urdf/analyze, a 400 means "URDF is invalid  fix it before analyzing".
#   That IS an error for analyze() callers  they need to validate first.
#   Only validate() should swallow 400 and convert it to a result.

from .models import ValidationResult, AnalysisResult

# URDF files must be <= 1MB (API enforces this)
URDF_MAX_SIZE_BYTES = 1 * 1024 * 1024


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
            ValidationResult with:
              .is_valid  (bool)   - True if all 9 checks pass
              .errors    (list)   - list of error strings if invalid, empty if valid

        Raises:
            FileNotFoundError   if file does not exist
            ValueError          if file is wrong extension or too large
            AuthError           if API key is invalid (HTTP 401)
            QuotaError          if monthly quota exceeded (HTTP 429)
            RoboInfraError      for server errors (HTTP 5xx) or other failures

        NOTE: HTTP 400 (invalid URDF) is returned as ValidationResult(is_valid=False),
              NOT as a raised exception. This is intentional  an invalid URDF is a
              valid outcome of validation, not an error condition.

        Example:
            result = client.urdf.validate("robot.urdf")
            if result.is_valid:
                print("Valid!")
            else:
                for error in result.errors:
                    print(f"  Error: {error}")
        """
        import os
        from .client import RoboInfraError
        import json as _json

        # Client-side validation - fail fast before any HTTP call
        safe_path = self._client._validate_file(
            file_path,
            allowed_extensions=[".urdf"]
        )

        # URDF-specific size limit (API enforces 1MB, we check locally first)
        size = os.path.getsize(safe_path)
        if size > URDF_MAX_SIZE_BYTES:
            raise ValueError(
                f"URDF file is {size / 1024:.0f}KB - maximum allowed is 1MB. "
                f"Reduce mesh references or split the file."
            )

        # ── POST to API and handle the response ───────────────────────────────
        try:
            raw = self._client._post_file("/api/urdf/validate", safe_path)
        except RoboInfraError as e:
            # ── BUG FIX ───────────────────────────────────────────────────────
            # HTTP 400 from /api/urdf/validate = structurally invalid URDF.
            # The API includes the validation errors in the response body:
            #   { "data": { "isValid": false, "errors": ["Root element must be <robot>", ...] } }
            #
            # We parse the body and return ValidationResult(is_valid=False, errors=[...])
            # instead of re-raising  this is a validation RESULT, not an API error.
            #
            # All other errors (401, 403, 429, 5xx) are re-raised as-is.
            if e.status_code == 400 and e.response_body:
                try:
                    body = _json.loads(e.response_body)
                    data = body.get("data", {})

                    # Confirm the body has validation result fields
                    if "isValid" in data or "errors" in data:
                        return ValidationResult(data)

                    # Fallback: no data.errors  try parsing the message field
                    # API message format: "Error 1 | Error 2 | Error 3"
                    msg = body.get("message", "")
                    if msg:
                        errors = [part.strip() for part in msg.split("|") if part.strip()]
                        return ValidationResult({"isValid": False, "errors": errors})

                except (_json.JSONDecodeError, Exception):
                    pass  # JSON parse failed  fall through to re-raise

            # Re-raise for all other cases:
            # 401 AuthError, 403 PlanError, 429 QuotaError, 5xx server errors,
            # or 400 where the body doesn't look like a validation result
            raise

        data = raw.get("data", raw)
        return ValidationResult(data)

    def analyze(self, file_path: str) -> "AnalysisResult":
        """
        Kinematic analysis - DOF, joint chain, end effectors.
        Requires Basic or Pro plan.

        The URDF must pass validation first  if the file is structurally
        invalid, the API returns 400 with the validation errors.

        Args:
            file_path: Path to your .urdf file. Max 1MB.

        Returns:
            AnalysisResult with:
              .robot_name     (str)   - robot name from <robot name="...">
              .link_count     (int)   - number of links
              .joint_count    (int)   - number of joints
              .dof            (int)   - degrees of freedom (non-fixed joints)
              .max_chain_depth (int)  - longest kinematic chain length
              .root_link      (str)   - root link name
              .end_effectors  (list)  - names of end effector links
              .joints         (list)  - list of dicts with joint details

        Raises:
            PlanError   if your plan is Free (requires Basic+)
            AuthError   if API key is invalid
            QuotaError  if monthly quota exceeded

        Example:
            result = client.urdf.analyze("robot.urdf")
            print(f"DOF: {result.dof}")
            print(f"End effectors: {result.end_effectors}")
            for joint in result.joints:
                print(f"  {joint['name']} ({joint['type']})")
        """
        safe_path = self._client._validate_file(
            file_path,
            allowed_extensions=[".urdf"]
        )
        raw = self._client._post_file("/api/urdf/analyze", safe_path)
        data = raw.get("data", raw)
        return AnalysisResult(data)