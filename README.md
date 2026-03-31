# roboinfra-sdk

Python SDK for RoboInfra Robotics API for URDF validation, kinematic analysis, 3D model conversion and mesh quality analysis.

[![PyPI version](https://badge.fury.io/py/roboinfra-sdk.svg)](https://pypi.org/project/roboinfra-sdk/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

**API:** `https://roboinfra-api.azurewebsites.net`  
**Dashboard:** `https://roboinfra-dashboard.azurewebsites.net`  
**PyPI:** `https://pypi.org/project/roboinfra-sdk/`  
**GitHub Action:** `uses: roboinfra/validate-urdf-action@v1`

---

## Installation

```bash
pip install roboinfra-sdk
```

---

## Quick Start

```python
import roboinfra as roboinfra

# Create client with your API key from the dashboard
client = roboinfra.Client("rk_your_api_key_here")

# 1. Check API health (no auth needed)
status = client.health()
print(status["status"])          # "Healthy"

# 2. Validate a URDF file (Free plan)
result = client.urdf.validate("robot.urdf")
if result.is_valid:
    print("URDF is valid!")
else:
    for error in result.errors:
        print(f"  Error: {error}")

# 3. Kinematic analysis (Basic + Pro plan)
analysis = client.urdf.analyze("robot.urdf")
print(f"DOF: {analysis.dof}")
print(f"End effectors: {analysis.end_effectors}")

# 4. Convert 3D model (Pro plan)
output = client.model.convert("robot.obj", "fbx", "robot.fbx")
print(f"Saved: {output}")

# 5. Mesh quality analysis (Pro plan)
mesh = client.model.analyze("robot.stl")
print(f"Triangles: {mesh.total_triangles}")
print(f"Watertight: {mesh.is_watertight}")
if not mesh.is_watertight:
    print("WARNING: mesh has holes  will cause physics simulation issues!")
```

---

## Get an API Key

1. Register at [roboinfra-dashboard.azurewebsites.net](https://roboinfra-dashboard.azurewebsites.net)
2. Go to **API Keys** → Create key
3. Keys start with `rk_`
4. Free plan: 50 calls/month for URDF validation  no credit card required

---

## API Reference

### `client.health()`  Public, no key needed

Check API connectivity and service status.

```python
result = client.health()
# Returns dict:
# {
#   "status": "Healthy",
#   "version": "1.0.0",
#   "uptime": "2d 4h 12m"
# }
```

---

### `client.urdf.validate(file_path)`  All plans (Free/Basic/Pro)

Validates a URDF file against 9 structural checks.

```python
result = client.urdf.validate("robot.urdf")

result.is_valid   # bool   True if all 9 checks pass
result.errors     # list   empty when valid, list of strings when invalid
```

**9 checks performed:**
1. Root element must be `<robot>`
2. At least one `<link>` must exist
3. No duplicate link names
4. No duplicate joint names
5. All joint `parent` links must reference a defined link
6. All joint `child` links must reference a defined link
7. Joint `type` must be valid (revolute, continuous, prismatic, fixed, floating, planar)
8. `revolute` and `prismatic` joints must include `<limit>`
9. Exactly one root link (no cycles, no orphans)

**Valid URDF example:**
```python
result = client.urdf.validate("robot.urdf")
# result.is_valid → True
# result.errors   → []
```

**Invalid URDF example:**
```python
result = client.urdf.validate("bad_robot.urdf")
# result.is_valid → False
# result.errors   → [
#     "Root element must be <robot>",
#     "At least one <link> must exist"
# ]
```

---

### `client.urdf.analyze(file_path)`  Basic + Pro plan

Kinematic analysis  DOF, joint chain, end effectors.

```python
result = client.urdf.analyze("robot.urdf")

result.robot_name      # str    name from <robot name="...">
result.link_count      # int    total links
result.joint_count     # int    total joints
result.dof             # int    degrees of freedom (non-fixed joints)
result.max_chain_depth # int    longest kinematic chain
result.root_link       # str    root link name
result.end_effectors   # list   end effector link names
result.joints          # list   joint details
```

**Example:**
```python
result = client.urdf.analyze("robot.urdf")
# result.robot_name      → "sample_arm"
# result.dof             → 2
# result.end_effectors   → ["tool0"]
# result.joints[0]       → {"name": "joint_1", "type": "revolute",
#                            "parent": "base_link", "child": "link_1"}
```

---

### `client.model.convert(file_path, target_format, output_path)`  Pro plan

Convert 3D model files between formats. No Blender required.

```python
output = client.model.convert("robot.stl", "obj", "robot.obj")
# Returns absolute path to saved output file

# All supported conversions:
# .fbx  → obj, stl, glb, gltf
# .obj  → stl, glb, gltf, fbx
# .stl  → obj, glb, gltf
# .gltf → obj, stl, glb
# .glb  → obj, stl, gltf
# .dae  → obj, stl, glb
# .3ds  → obj, stl, glb
# .blend→ obj, stl, glb
```

**Examples:**
```python
client.model.convert("robot.stl", "obj",  "robot.obj")
client.model.convert("robot.obj", "fbx",  "robot.fbx")
client.model.convert("robot.fbx", "glb",  "robot.glb")
client.model.convert("robot.obj", "gltf", "robot.gltf")
```

---

### `client.model.analyze(file_path)`  Pro plan

Mesh quality analysis for physics simulation readiness.

```python
result = client.model.analyze("robot.stl")

result.mesh_count       # int    number of mesh objects
result.total_vertices   # int    total vertex count
result.total_triangles  # int    triangle count after triangulation
result.material_count   # int    number of materials
result.has_bones        # bool   True if skeletal data detected
result.is_watertight    # bool   True if ALL meshes are watertight (required for physics)
result.bounding_box     # dict   {"x": 0.42, "y": 0.38, "z": 0.75}
result.center_of_mass   # dict   {"x": 0.0, "y": 0.0, "z": 0.21}
result.meshes           # list   per-mesh breakdown
```

**Example:**
```python
result = client.model.analyze("robot_arm.stl")
# result.total_triangles → 30240
# result.is_watertight   → True
# result.bounding_box    → {"x": 0.42, "y": 0.38, "z": 0.75}

if not result.is_watertight:
    print("WARNING: mesh has holes  robot will fall through ground in Gazebo!")
```

---

## Error Handling

```python
from roboinfra import (
    RoboInfraError,   # base  any API error
    AuthError,        # 401  invalid API key
    PlanError,        # 403  endpoint requires higher plan
    QuotaError,       # 429  monthly quota exceeded
)

try:
    result = client.urdf.validate("robot.urdf")
except AuthError:
    print("Invalid API key  get one at roboinfra-dashboard.azurewebsites.net/keys")
except PlanError:
    print("Upgrade your plan at roboinfra-dashboard.azurewebsites.net/subscription")
except QuotaError:
    print("Monthly quota exceeded  upgrade or wait until next month")
except RoboInfraError as e:
    print(f"API error: {e} (HTTP {e.status_code})")
```

> **Note:** 400 errors (bad file, oversized file) also count against your monthly quota.
> The SDK validates file size and extension **locally before any HTTP call** to avoid
> wasting quota on obvious errors.

---

## Plans and Limits

| Plan | Price | Quota | Features |
|------|-------|-------|---------|
| Free | $0/month | 50 calls | URDF validation only |
| Basic | $25/month | 500 calls | URDF validation + kinematic analysis |
| Pro | $75/month | 5,000 calls | All features (3D conversion + mesh analysis) |

---

## File Limits

| Endpoint | Max file size | Allowed extensions |
|----------|--------------|-------------------|
| `urdf.validate` | **1 MB** | `.urdf` |
| `urdf.analyze` | **1 MB** | `.urdf` |
| `model.convert` | **20 MB** | `.fbx .obj .stl .gltf .glb .dae .3ds .blend` |
| `model.analyze` | **20 MB** | `.fbx .obj .stl .gltf .glb .dae .3ds .blend` |

The SDK validates file size and extension **locally before any HTTP call**  no wasted quota on obvious errors.

---

## CI/CD Integration

### Option 1  GitHub Action (simplest, recommended)

No Python required. Just add 3 lines to your workflow:

```yaml
# .github/workflows/validate-urdf.yml
name: Validate URDF
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: roboinfra/validate-urdf-action@v1
        with:
          api-key: ${{ secrets.ROBOINFRA_API_KEY }}
          file: urdf/robot.urdf
```

Full docs: [github.com/roboinfra/validate-urdf-action](https://github.com/Ravindar10/validate-urdf-action)

---

### Option 2  SDK inside a run step (more control)

Use this approach when you need custom logic  multiple files, conditional checks, or integration with other tools:

```yaml
- name: Validate URDF
  run: |
    pip install roboinfra-sdk
    python - <<'EOF'
    import roboinfra as roboinfra
    import sys
    client = roboinfra.Client("${{ secrets.ROBOINFRA_API_KEY }}")
    result = client.urdf.validate("urdf/robot.urdf")
    if not result.is_valid:
        print("URDF validation failed:")
        for e in result.errors:
            print(f"  - {e}")
        sys.exit(1)
    print("URDF valid!")
    EOF
```

---

## License

MIT