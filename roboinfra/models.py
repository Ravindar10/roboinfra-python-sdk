# FILE: roboinfra/models.py
#
# Response data classes.
# Each class wraps the raw API JSON dict and exposes Python-friendly attributes.
# Attribute names use snake_case (Python convention), matching camelCase from API.


class ValidationResult:
    """
    Result from client.urdf.validate()

    Attributes:
        is_valid (bool):   True if URDF passes all 9 checks
        errors   (list):   List of error strings. Empty when is_valid=True.

    Real example when VALID:
        result.is_valid → True
        result.errors   → []

    Real example when INVALID:
        result.is_valid → False
        result.errors   → [
            "Root element must be <robot>",
            "At least one <link> must exist"
        ]
    """
    def __init__(self, data: dict):
        self.is_valid: bool = data.get("isValid", False)
        self.errors:   list = data.get("errors",  [])

    def __repr__(self):
        if self.is_valid:
            return "<ValidationResult valid=True>"
        return f"<ValidationResult valid=False errors={len(self.errors)}>"


class AnalysisResult:
    """
    Result from client.urdf.analyze()

    Attributes:
        robot_name      (str):   Name from <robot name="...">
        link_count      (int):   Total number of links
        joint_count     (int):   Total number of joints
        dof             (int):   Degrees of freedom (non-fixed joints)
        max_chain_depth (int):   Longest kinematic chain
        root_link       (str):   Name of the root link
        end_effectors   (list):  Names of end-effector links
        joints          (list):  List of joint dicts:
                                   [{"name": "joint_1", "type": "revolute",
                                     "parent": "base_link", "child": "link_1"}]

    Real example:
        result.robot_name      → "sample_arm"
        result.dof             → 2
        result.end_effectors   → ["tool0"]
        result.joints[0]       → {"name": "joint_1", "type": "revolute",
                                   "parent": "base_link", "child": "link_1"}
    """
    def __init__(self, data: dict):
        self.robot_name:       str  = data.get("robotName",     "")
        self.link_count:       int  = data.get("linkCount",      0)
        self.joint_count:      int  = data.get("jointCount",     0)
        self.dof:              int  = data.get("dof",            0)
        self.max_chain_depth:  int  = data.get("maxChainDepth",  0)
        self.root_link:        str  = data.get("rootLink",       "")
        self.end_effectors:    list = data.get("endEffectors",  [])
        self.joints:           list = data.get("joints",        [])

    def __repr__(self):
        return (f"<AnalysisResult robot='{self.robot_name}' "
                f"dof={self.dof} links={self.link_count} joints={self.joint_count}>")


class MeshAnalysisResult:
    """
    Result from client.model.analyze()

    Attributes:
        mesh_count      (int):   Number of mesh objects in the file
        total_vertices  (int):   Total vertex count across all meshes
        total_triangles (int):   Total triangle count after triangulation
        material_count  (int):   Number of materials
        has_bones       (bool):  True if skeletal/rigged data detected
        is_watertight   (bool):  True if ALL meshes are watertight (required for physics)
        bounding_box    (dict):  {"x": 0.42, "y": 0.38, "z": 0.75}  (model units)
        center_of_mass  (dict):  {"x": 0.0, "y": 0.0, "z": 0.21}
        meshes          (list):  Per-mesh breakdown:
                                   [{"name": "base_mesh", "vertices": 8420,
                                     "triangles": 16240, "isWatertight": true,
                                     "hasBones": false}]

    Real example for a 2-mesh robot arm:
        result.mesh_count      → 2
        result.total_triangles → 30240
        result.is_watertight   → True
        result.bounding_box    → {"x": 0.42, "y": 0.38, "z": 0.75}
        result.center_of_mass  → {"x": 0.0, "y": 0.0, "z": 0.21}
    """
    def __init__(self, data: dict):
        self.mesh_count:      int  = data.get("meshCount",      0)
        self.total_vertices:  int  = data.get("totalVertices",  0)
        self.total_triangles: int  = data.get("totalTriangles", 0)
        self.material_count:  int  = data.get("materialCount",  0)
        self.has_bones:       bool = data.get("hasBones",       False)
        self.is_watertight:   bool = data.get("isWatertight",   False)
        self.bounding_box:    dict = data.get("boundingBox",    {})
        self.center_of_mass:  dict = data.get("centerOfMass",  {})
        self.meshes:          list = data.get("meshes",         [])

    def __repr__(self):
        return (f"<MeshAnalysisResult meshes={self.mesh_count} "
                f"tris={self.total_triangles} watertight={self.is_watertight}>")