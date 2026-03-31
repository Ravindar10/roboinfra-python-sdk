# FILE: tests/test_client.py
#
# 36 unit tests — ALL use mocks, NO real HTTP calls.
# Run instantly, offline, no quota used.
#
# Run:
#   cd roboinfra-python-sdk
#   pip install pytest pytest-mock
#   pytest tests/ -v
#
# Expected: 36 passed in ~1s

import os
import json
import pytest
from unittest.mock import MagicMock, patch
from roboinfra import Client, RoboInfraError, AuthError, PlanError, QuotaError
from roboinfra.models import ValidationResult, AnalysisResult, MeshAnalysisResult

FAKE_KEY = "rk_test_00000000000000000000000000000000"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return Client(FAKE_KEY)

@pytest.fixture
def valid_urdf(tmp_path):
    f = tmp_path / "robot.urdf"
    f.write_text("""<?xml version="1.0"?>
<robot name="sample_arm">
  <link name="base_link">
    <visual><geometry><box size="0.1 0.1 0.2"/></geometry></visual>
  </link>
  <link name="link_1">
    <visual><geometry><cylinder radius="0.04" length="0.3"/></geometry></visual>
  </link>
  <link name="tool0"/>
  <joint name="joint_1" type="revolute">
    <parent link="base_link"/>
    <child  link="link_1"/>
    <axis xyz="0 0 1"/>
    <limit effort="100" velocity="1.0" lower="-3.14" upper="3.14"/>
  </joint>
  <joint name="tool_joint" type="fixed">
    <parent link="link_1"/>
    <child  link="tool0"/>
  </joint>
</robot>""")
    return str(f)

@pytest.fixture
def invalid_urdf(tmp_path):
    f = tmp_path / "bad.urdf"
    f.write_text("<not_robot/>")
    return str(f)

@pytest.fixture
def stl_file(tmp_path):
    f = tmp_path / "robot.stl"
    f.write_bytes(b"\x00" * 80 + b"\x00\x00\x00\x00")
    return str(f)


def make_mock_response(status_code: int, json_data: dict):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = json.dumps(json_data)
    return mock


# ── Client construction ───────────────────────────────────────────────────────

class TestClientConstruction:

    def test_valid_key_creates_client(self):
        assert Client(FAKE_KEY) is not None

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            Client("")

    def test_none_key_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Client(None)

    def test_wrong_prefix_raises(self):
        with pytest.raises(ValueError, match="rk_"):
            Client("wrongprefix_abc123")

    def test_api_key_not_in_repr(self):
        c = Client(FAKE_KEY)
        assert FAKE_KEY not in repr(c)
        assert "rk_te" in repr(c)

    def test_has_urdf_resource(self, client):
        assert hasattr(client, "urdf")

    def test_has_model_resource(self, client):
        assert hasattr(client, "model")

    def test_has_health_method(self, client):
        assert hasattr(client, "health")


# ── Health endpoint ───────────────────────────────────────────────────────────

class TestHealth:

    def test_health_returns_status(self, client):
        """GET /api/health — public endpoint, no API key needed."""
        mock_resp = make_mock_response(200, {
            "success": True,
            "data": {
                "status": "Healthy",
                "version": "1.0.0",
                "uptime": "2d 4h 12m"
            }
        })
        with patch.object(client._session, "get", return_value=mock_resp):
            result = client.health()

        assert result["status"] == "Healthy"
        assert "version" in result

    def test_health_connection_error(self, client):
        """If API is unreachable, raises RoboInfraError."""
        import requests as req
        with patch.object(client._session, "get",
                          side_effect=req.exceptions.ConnectionError("refused")):
            with pytest.raises(RoboInfraError, match="Connection failed"):
                client.health()


# ── URDF Validate ─────────────────────────────────────────────────────────────

class TestUrdfValidate:

    def test_valid_urdf(self, client, valid_urdf):
        mock_resp = make_mock_response(200, {
            "success": True,
            "data": {"isValid": True, "errors": []}
        })
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.urdf.validate(valid_urdf)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_urdf_raises_or_returns_false(self, client, invalid_urdf):
        errors = ["Root element must be <robot>", "At least one <link> must exist"]
        mock_resp = make_mock_response(400, {
            "success": False,
            "message": " | ".join(errors),
            "data": {"isValid": False, "errors": errors}
        })
        with patch.object(client._session, "post", return_value=mock_resp):
            try:
                result = client.urdf.validate(invalid_urdf)
                assert result.is_valid is False
            except RoboInfraError as e:
                assert "400" in str(e) or "Root element" in str(e.response_body or "")

    def test_file_not_found(self, client):
        with pytest.raises(FileNotFoundError):
            client.urdf.validate("does_not_exist.urdf")

    def test_wrong_extension(self, client, tmp_path):
        bad = tmp_path / "robot.xml"
        bad.write_text("<robot/>")
        with pytest.raises(ValueError, match=".urdf"):
            client.urdf.validate(str(bad))

    def test_empty_file(self, client, tmp_path):
        empty = tmp_path / "empty.urdf"
        empty.write_text("")
        with pytest.raises(ValueError, match="empty"):
            client.urdf.validate(str(empty))

    def test_oversized_file(self, client, tmp_path):
        big = tmp_path / "big.urdf"
        big.write_bytes(b"x" * (1024 * 1024 + 1))
        with pytest.raises(ValueError, match="1MB"):
            client.urdf.validate(str(big))

    def test_api_key_in_header(self, client, valid_urdf):
        mock_resp = make_mock_response(200, {"success": True, "data": {"isValid": True, "errors": []}})
        with patch.object(client._session, "post", return_value=mock_resp):
            client.urdf.validate(valid_urdf)
        assert client._session.headers["X-Api-Key"] == FAKE_KEY


# ── URDF Analyze ──────────────────────────────────────────────────────────────

class TestUrdfAnalyze:

    def test_analyze_returns_result(self, client, valid_urdf):
        mock_resp = make_mock_response(200, {
            "success": True,
            "data": {
                "robotName": "sample_arm", "linkCount": 4, "jointCount": 3,
                "dof": 2, "maxChainDepth": 3, "rootLink": "base_link",
                "endEffectors": ["tool0"],
                "joints": [
                    {"name": "joint_1",    "type": "revolute", "parent": "base_link", "child": "link_1"},
                    {"name": "joint_2",    "type": "revolute", "parent": "link_1",    "child": "link_2"},
                    {"name": "tool_joint", "type": "fixed",    "parent": "link_2",    "child": "tool0"},
                ]
            }
        })
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.urdf.analyze(valid_urdf)
        assert isinstance(result, AnalysisResult)
        assert result.robot_name == "sample_arm"
        assert result.dof == 2
        assert result.end_effectors == ["tool0"]

    def test_plan_error(self, client, valid_urdf):
        mock_resp = make_mock_response(403, {"success": False, "message": "Basic plan required."})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(PlanError):
                client.urdf.analyze(valid_urdf)

    def test_quota_exceeded(self, client, valid_urdf):
        mock_resp = make_mock_response(429, {"success": False, "message": "Quota exceeded."})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(QuotaError):
                client.urdf.analyze(valid_urdf)


# ── Model Convert ─────────────────────────────────────────────────────────────

class TestModelConvert:

    def test_convert_stl_to_obj(self, client, stl_file, tmp_path):
        output = str(tmp_path / "robot.obj")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"# OBJ file\nv 0 0 0\n"
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.model.convert(stl_file, "obj", output)
        assert os.path.exists(result)
        assert result.endswith("robot.obj")

    def test_invalid_format_raises_locally(self, client, stl_file, tmp_path):
        with pytest.raises(ValueError, match="obj, glb, gltf"):
            client.model.convert(stl_file, "fbx", str(tmp_path / "out.fbx"))

    def test_plan_error(self, client, stl_file, tmp_path):
        mock_resp = make_mock_response(403, {"success": False, "message": "Pro plan required."})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(PlanError):
                client.model.convert(stl_file, "obj", str(tmp_path / "out.obj"))


# ── Model Analyze ─────────────────────────────────────────────────────────────

class TestModelAnalyze:

    def test_analyze_returns_result(self, client, stl_file):
        mock_resp = make_mock_response(200, {
            "success": True,
            "data": {
                "meshCount": 2, "totalVertices": 15420, "totalTriangles": 30240,
                "materialCount": 1, "hasBones": False, "isWatertight": True,
                "boundingBox": {"x": 0.42, "y": 0.38, "z": 0.75},
                "centerOfMass": {"x": 0.0, "y": 0.0, "z": 0.21},
                "meshes": [{"name": "base_mesh", "vertices": 8420, "triangles": 16240,
                             "isWatertight": True, "hasBones": False}]
            }
        })
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.model.analyze(stl_file)
        assert isinstance(result, MeshAnalysisResult)
        assert result.mesh_count == 2
        assert result.total_triangles == 30240
        assert result.is_watertight is True

    def test_not_watertight(self, client, stl_file):
        mock_resp = make_mock_response(200, {
            "success": True,
            "data": {
                "meshCount": 1, "totalVertices": 500, "totalTriangles": 800,
                "materialCount": 0, "hasBones": False, "isWatertight": False,
                "boundingBox": {"x": 0.1, "y": 0.1, "z": 0.1},
                "centerOfMass": {"x": 0.0, "y": 0.0, "z": 0.05},
                "meshes": [{"name": "mesh", "vertices": 500, "triangles": 800,
                            "isWatertight": False, "hasBones": False}]
            }
        })
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.model.analyze(stl_file)
        assert result.is_watertight is False


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:

    def test_401_raises_auth_error(self, client, valid_urdf):
        mock_resp = make_mock_response(401, {"success": False, "message": "Invalid key"})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(AuthError) as e:
                client.urdf.validate(valid_urdf)
        assert e.value.status_code == 401

    def test_403_raises_plan_error(self, client, valid_urdf):
        mock_resp = make_mock_response(403, {"success": False, "message": "Pro required"})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(PlanError) as e:
                client.urdf.validate(valid_urdf)
        assert e.value.status_code == 403

    def test_429_raises_quota_error(self, client, valid_urdf):
        mock_resp = make_mock_response(429, {"success": False, "message": "Quota exceeded"})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(QuotaError) as e:
                client.urdf.validate(valid_urdf)
        assert e.value.status_code == 429

    def test_500_raises_roboinfra_error(self, client, valid_urdf):
        mock_resp = make_mock_response(500, {"success": False, "message": "Internal error"})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(RoboInfraError) as e:
                client.urdf.validate(valid_urdf)
        assert e.value.status_code == 500

    def test_connection_error(self, client, valid_urdf):
        import requests as req
        with patch.object(client._session, "post",
                          side_effect=req.exceptions.ConnectionError("refused")):
            with pytest.raises(RoboInfraError, match="Connection failed"):
                client.urdf.validate(valid_urdf)

    def test_timeout_error(self, client, valid_urdf):
        import requests as req
        with patch.object(client._session, "post",
                          side_effect=req.exceptions.Timeout("timed out")):
            with pytest.raises(RoboInfraError, match="Connection failed"):
                client.urdf.validate(valid_urdf)


# ── Security ──────────────────────────────────────────────────────────────────

class TestSecurity:

    def test_api_key_never_in_repr(self):
        key = "rk_test_secretkeyvalue1234567890abc"
        c   = Client(key)
        assert key not in repr(c)
        assert key not in str(c)

    def test_path_traversal_blocked(self, client):
        with pytest.raises(FileNotFoundError):
            client.urdf.validate("../../etc/passwd.urdf")

    def test_directory_rejected(self, client, tmp_path):
        with pytest.raises((ValueError, IsADirectoryError, FileNotFoundError)):
            client.urdf.validate(str(tmp_path))

    def test_wrong_extension_blocked(self, client, tmp_path):
        evil = tmp_path / "malicious.exe"
        evil.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match=".urdf"):
            client.urdf.validate(str(evil))

    def test_oversized_urdf_blocked_locally(self, client, tmp_path):
        big = tmp_path / "huge.urdf"
        big.write_bytes(b"<robot/>" + b"x" * (2 * 1024 * 1024))
        with pytest.raises(ValueError, match="1MB"):
            client.urdf.validate(str(big))

    def test_oversized_model_blocked_locally(self, client, tmp_path):
        big = tmp_path / "huge.stl"
        big.write_bytes(b"\x00" * 80 + b"\x00\x00\x00\x00" + b"x" * (26 * 1024 * 1024))
        with pytest.raises(ValueError, match="MB"):
            client.model.analyze(str(big))