# FILE: roboinfra/urdf.py
# Phase 13 — added diff() method

from .models import ValidationResult, AnalysisResult, DiffResult

URDF_MAX_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB


class UrdfResource:
    """
    URDF validation, kinematic analysis, and semantic diff.

    Access via:
        client = roboinfra.Client("rk_xxx")
        client.urdf.validate("robot.urdf")
        client.urdf.analyze("robot.urdf")
        client.urdf.diff("old.urdf", "new.urdf")
    """

    def __init__(self, client):
        self._client = client

    def validate(self, file_path: str) -> "ValidationResult":
        """
        Validate a URDF file against 9 structural checks.
        Available on ALL plans (Free, Basic, Pro).

        Args:
            file_path: Path to your .urdf or .xacro file. Max 1MB.

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
            data = (raw.get("data") or {})
            return ValidationResult(data)

        except RoboInfraError as e:
            if e.status_code == 400 and e.response_body:
                try:
                    body = _json.loads(e.response_body)
                    data = body.get("data") or {}
                    is_valid = data.get("isValid", False)
                    errors = data.get("errors") or []
                    if not errors and not is_valid:
                        msg = body.get("message", "")
                        errors = [p.strip() for p in msg.split("|") if p.strip()]
                    return ValidationResult({"isValid": is_valid, "errors": errors})
                except (_json.JSONDecodeError, Exception):
                    pass
            raise

    def analyze(self, file_path: str) -> "AnalysisResult":
        """
        Kinematic analysis — DOF, joint chain, end effectors.
        Requires Basic or Pro plan.

        Args:
            file_path: Path to your .urdf or .xacro file. Max 1MB.

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

    def diff(self, old_file_path: str, new_file_path: str) -> "DiffResult":
        """
        Semantic diff between two URDF files.
        Detects added/removed/changed links, joints, limits, origins, geometry, mass.
        Requires Basic or Pro plan.

        Args:
            old_file_path: Path to the old (baseline) .urdf or .xacro file.
            new_file_path: Path to the new (changed) .urdf or .xacro file.

        Returns:
            DiffResult:
              .has_changes     bool  — True if any differences found
              .total_changes   int   — number of change entries
              .old_robot_name  str   — robot name from old file
              .new_robot_name  str   — robot name from new file
              .summary         dict  — {links_added, links_removed, joints_added, ...}
              .changes         list  — list of change dicts with action/element/name/field/old/new

        Raises:
            PlanError   if plan is Free (requires Basic+)
            AuthError   if API key is invalid
            QuotaError  if monthly quota exceeded

        Example:
            result = client.urdf.diff("robot_v1.urdf", "robot_v2.urdf")
            if result.has_changes:
                for c in result.changes:
                    print(f"  {c['action']} {c['element']} {c['name']}: {c.get('field','')}")
        """
        import os

        old_safe = self._client._validate_file(
            old_file_path, allowed_extensions=[".urdf", ".xacro"]
        )
        new_safe = self._client._validate_file(
            new_file_path, allowed_extensions=[".urdf", ".xacro"]
        )

        for p in [old_safe, new_safe]:
            size = os.path.getsize(p)
            if size > URDF_MAX_SIZE_BYTES:
                raise ValueError(
                    f"File '{os.path.basename(p)}' is {size / 1024:.0f}KB — max 1MB."
                )

        raw = self._client._post_two_files(
            "/api/urdf/diff", old_safe, new_safe,
            field_names=("oldFile", "newFile")
        )
        data = (raw.get("data") or {})
        return DiffResult(data)