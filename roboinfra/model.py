# FILE: roboinfra/model.py
#
# 3D Model endpoint wrappers.
#
# ── Endpoint 1: POST /api/model/convert?targetFormat=obj ─────────────────────
# Pro plan only. Max file size: 20MB.
#
# Request:
#   POST /api/model/convert?targetFormat=obj
#   multipart/form-data
#   file: robot.stl
#   X-Api-Key: rk_xxx
#
# Response (success):
#   HTTP 200
#   Content-Disposition: attachment; filename="robot.obj"
#   Content-Type: text/plain
#   <binary file content — save directly to disk>
#
# Response (error):
#   HTTP 400
#   { "success": false, "message": "Cannot convert .stl to fbx. Allowed: obj, glb, gltf" }
#
# Supported conversions:
#   .fbx  → obj, stl, glb, gltf
#   .obj  → stl, glb, gltf, fbx
#   .stl  → obj, glb, gltf
#   .gltf → obj, stl, glb
#   .glb  → obj, stl, gltf
#   .dae  → obj, stl, glb
#   .3ds  → obj, stl, glb
#   .blend→ obj, stl, glb
#
# ── Endpoint 2: POST /api/model/analyze ──────────────────────────────────────
# Pro plan only. Max file size: 20MB.
#
# Response (success):
#   HTTP 200
#   {
#     "success": true,
#     "data": {
#       "meshCount": 2,
#       "totalVertices": 15420,
#       "totalTriangles": 30240,
#       "materialCount": 1,
#       "hasBones": false,
#       "isWatertight": true,
#       "boundingBox": { "x": 0.42, "y": 0.38, "z": 0.75 },
#       "centerOfMass": { "x": 0.0, "y": 0.0, "z": 0.21 },
#       "meshes": [
#         {
#           "name": "base_mesh",
#           "vertices": 8420,
#           "triangles": 16240,
#           "isWatertight": true,
#           "hasBones": false
#         }
#       ]
#     }
#   }

import os

# Allowed extensions for 3D model endpoints
MODEL_EXTENSIONS = [".fbx", ".obj", ".stl", ".gltf", ".glb", ".dae", ".3ds", ".blend"]

# Valid output formats per input extension
VALID_CONVERSIONS = {
    ".fbx":   ["obj", "stl", "glb", "gltf"],
    ".obj":   ["stl", "glb", "gltf", "fbx"],
    ".stl":   ["obj", "glb", "gltf"],
    ".gltf":  ["obj", "stl", "glb"],
    ".glb":   ["obj", "stl", "gltf"],
    ".dae":   ["obj", "stl", "glb"],
    ".3ds":   ["obj", "stl", "glb"],
    ".blend": ["obj", "stl", "glb"],
}

from .models import MeshAnalysisResult


class ModelResource:
    """
    3D model conversion and mesh analysis.
    Both endpoints require a Pro plan.

    Access via:
        client.model.convert("robot.stl", "obj", "output/robot.obj")
        client.model.analyze("robot.stl")
    """

    def __init__(self, client):
        self._client = client

    def convert(self, file_path: str, target_format: str, output_path: str) -> str:
        """
        Convert a 3D model to another format.
        Requires Pro plan. Max file size: 20MB.

        Args:
            file_path:     Path to your input 3D file (.fbx, .stl, .obj, etc.)
            target_format: Output format string: "obj", "stl", "glb", "gltf", "fbx"
            output_path:   Where to save the converted file (e.g. "output/robot.obj")

        Returns:
            Absolute path to the saved output file.

        Raises:
            ValueError   if format is invalid for this input file type
            PlanError    if not on Pro plan
            QuotaError   if quota exceeded
            FileNotFoundError if input file not found

        Example:
            # Convert STL to OBJ
            out = client.model.convert("robot.stl", "obj", "robot.obj")
            print(f"Saved to: {out}")

            # Convert FBX to GLB
            out = client.model.convert("robot.fbx", "glb", "robot.glb")

            # Convert OBJ to GLTF
            out = client.model.convert("robot.obj", "gltf", "robot.gltf")
        """
        safe_path = self._client._validate_file(file_path, allowed_extensions=MODEL_EXTENSIONS)

        # Validate target format locally before making HTTP call
        target = target_format.lower().lstrip(".")
        ext    = os.path.splitext(safe_path)[1].lower()
        allowed = VALID_CONVERSIONS.get(ext, [])
        if target not in allowed:
            raise ValueError(
                f"Cannot convert {ext} to '{target}'. "
                f"Allowed output formats for {ext}: {', '.join(allowed)}"
            )

        return self._client._post_file_download(
            "/api/model/convert",
            safe_path,
            output_path,
            params={"targetFormat": target}
        )

    def analyze(self, file_path: str) -> "MeshAnalysisResult":
        """
        Analyze 3D mesh quality — triangles, vertices, watertight check, CoM.
        Requires Pro plan. Max file size: 20MB.

        Use this to check if a mesh is suitable for physics simulation.
        Non-watertight meshes will cause objects to fall through each other in Gazebo/MoveIt.

        Args:
            file_path: Path to your 3D file (.stl, .obj, .fbx, .glb, etc.)

        Returns:
            MeshAnalysisResult with:
              .mesh_count      (int)   — number of mesh objects
              .total_vertices  (int)   — total vertex count
              .total_triangles (int)   — total triangle count
              .material_count  (int)   — number of materials
              .has_bones       (bool)  — True if skeletal/rigged data present
              .is_watertight   (bool)  — True if ALL meshes are watertight
              .bounding_box    (dict)  — {"x": float, "y": float, "z": float}
              .center_of_mass  (dict)  — {"x": float, "y": float, "z": float}
              .meshes          (list)  — per-mesh breakdown

        Raises:
            PlanError    if not on Pro plan
            QuotaError   if quota exceeded

        Example:
            result = client.model.analyze("robot.stl")
            print(f"Triangles: {result.total_triangles}")
            print(f"Watertight: {result.is_watertight}")
            if not result.is_watertight:
                print("WARNING: mesh has holes — will cause physics issues!")
            for mesh in result.meshes:
                print(f"  {mesh['name']}: {mesh['triangles']} tris, watertight={mesh['isWatertight']}")
        """
        safe_path = self._client._validate_file(file_path, allowed_extensions=MODEL_EXTENSIONS)
        raw  = self._client._post_file("/api/model/analyze", safe_path)
        data = raw.get("data", raw)
        return MeshAnalysisResult(data)