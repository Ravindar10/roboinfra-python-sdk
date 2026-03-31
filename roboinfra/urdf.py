# FILE: roboinfra/urdf.py
#
# URDF endpoint wrappers.
#
# ── Endpoint 1: POST /api/urdf/validate ──────────────────────────────────────
# All plans. Max file size: 1MB. Extension: .urdf only.
#
# Request:
#   multipart/form-data
#   file: robot.urdf (binary)
#   X-Api-Key: rk_xxx
#
# Response (valid URDF):
#   HTTP 200
#   {
#     "success": true,
#     "statusCode": 200,
#     "message": "URDF file is valid.",
#     "data": {
#       "isValid": true,
#       "errors": []
#     }
#   }
#
# Response (invalid URDF):
#   HTTP 400
#   {
#     "success": false,
#     "statusCode": 400,
#     "message": "Root element must be <robot> | At least one <link> must exist",
#     "data": {
#       "isValid": false,
#       "errors": [
#         "Root element must be <robot>",
#         "At least one <link> must exist"
#       ]
#     }
#   }
#
# ── Endpoint 2: POST /api/urdf/analyze ───────────────────────────────────────
# Basic + Pro plans only. Same file requirements.
#
# Response (success):
#   HTTP 200
#   {
#     "success": true,
#     "statusCode": 200,
#     "message": "Kinematic analysis complete.",
#     "data": {
#       "robotName": "sample_arm",
#       "linkCount": 4,
#       "jointCount": 3,
#       "dof": 2,
#       "maxChainDepth": 3,
#       "rootLink": "base_link",
#       "endEffectors": ["tool0"],
#       "joints": [
#         { "name": "joint_1", "type": "revolute", "parent": "base_link", "child": "link_1" },
#         { "name": "joint_2", "type": "revolute", "parent": "link_1",    "child": "link_2" },
#         { "name": "tool_joint", "type": "fixed", "parent": "link_2",   "child": "tool0"  }
#       ]
#     }
#   }

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
              .is_valid  (bool)   — True if all 9 checks pass
              .errors    (list)   — list of error strings if invalid

        Raises:
            FileNotFoundError   if file does not exist
            ValueError          if file is wrong extension or too large
            AuthError           if API key is invalid
            QuotaError          if monthly quota exceeded
            RoboInfraError      for other API errors

        Example:
            result = client.urdf.validate("robot.urdf")
            if result.is_valid:
                print("Valid!")
            else:
                for error in result.errors:
                    print(f"  Error: {error}")
        """
        from .client import MAX_FILE_SIZE_BYTES
        import os

        # Client-side validation — fail fast before any HTTP call
        safe_path = self._client._validate_file(
            file_path,
            allowed_extensions=[".urdf"]
        )

        # URDF-specific size limit (API enforces 1MB, we check locally first)
        size = os.path.getsize(safe_path)
        if size > URDF_MAX_SIZE_BYTES:
            raise ValueError(
                f"URDF file is {size / 1024:.0f}KB — maximum allowed is 1MB. "
                f"Reduce mesh references or split the file."
            )

        raw = self._client._post_file("/api/urdf/validate", safe_path)
        data = raw.get("data", raw)
        return ValidationResult(data)

    def analyze(self, file_path: str) -> "AnalysisResult":
        """
        Kinematic analysis — DOF, joint chain, end effectors.
        Requires Basic or Pro plan.

        The URDF must pass validation first — if the file is structurally
        invalid, the API returns 400 with the validation errors.

        Args:
            file_path: Path to your .urdf file. Max 1MB.

        Returns:
            AnalysisResult with:
              .robot_name     (str)   — robot name from <robot name="...">
              .link_count     (int)   — number of links
              .joint_count    (int)   — number of joints
              .dof            (int)   — degrees of freedom (non-fixed joints)
              .max_chain_depth (int)  — longest kinematic chain length
              .root_link      (str)   — root link name
              .end_effectors  (list)  — names of end effector links
              .joints         (list)  — list of dicts with joint details

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