"""Build the Block-words scene in a running Isaac Sim (run through the python server, see isaac/README.md).

Reads /workspace/data/blockworld.json (the repo is mounted read-only at /workspace) and
/workspace/isaac/letters/<X>.png. Everything here is a plain USD scene: blocks are placed by their pose,
there is no physics. Moving blocks later is kinematic (teleport / attach), as agreed.
"""
import json

import omni.usd
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdShade, Vt

DATA = json.load(open("/workspace/data/blockworld.json"))
TEXTURE = "/workspace/isaac/letters/%s.png"
EDGE = 0.05                    # block edge, metres
TOWER_SPACING = 0.18           # distance between the three towers
stage = omni.usd.get_context().get_stage()

for path in ("/World", "/Looks"):
    if stage.GetPrimAtPath(path):
        stage.RemovePrim(path)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
world = UsdGeom.Xform.Define(stage, "/World")
stage.SetDefaultPrim(world.GetPrim())


def block_mesh(path, edge):
    """A cube whose six faces each carry the full 0..1 texture, so the letter shows on every side."""
    h = edge / 2
    faces = [((0, 0, 1), [(-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]),
             ((0, 0, -1), [(-h, h, -h), (h, h, -h), (h, -h, -h), (-h, -h, -h)]),
             ((1, 0, 0), [(h, -h, -h), (h, h, -h), (h, h, h), (h, -h, h)]),
             ((-1, 0, 0), [(-h, h, -h), (-h, -h, -h), (-h, -h, h), (-h, h, h)]),
             ((0, 1, 0), [(h, h, -h), (-h, h, -h), (-h, h, h), (h, h, h)]),
             ((0, -1, 0), [(-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h)])]
    pts, normals, uvs = [], [], []
    for n, corners in faces:
        pts += corners
        normals += [n] * 4
        uvs += [(0, 0), (1, 0), (1, 1), (0, 1)]
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]))
    mesh.CreateFaceVertexCountsAttr([4] * 6)
    mesh.CreateFaceVertexIndicesAttr(list(range(24)))
    mesh.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*n) for n in normals]))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    st.Set(Vt.Vec2fArray([Gf.Vec2f(*uv) for uv in uvs]))
    return mesh


def letter_material(letter):
    mpath = f"/Looks/Block_{letter}"
    mat = UsdShade.Material.Define(stage, mpath)
    pbr = UsdShade.Shader.Define(stage, mpath + "/PBR")
    pbr.CreateIdAttr("UsdPreviewSurface")
    pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.55)
    pbr.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    reader = UsdShade.Shader.Define(stage, mpath + "/st")
    reader.CreateIdAttr("UsdPrimvarReader_float2")
    reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
    reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
    tex = UsdShade.Shader.Define(stage, mpath + "/tex")
    tex.CreateIdAttr("UsdUVTexture")
    tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(TEXTURE % letter)
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), "result")
    tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
    mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
    return mat


# table, top surface at z = 0
table = UsdGeom.Cube.Define(stage, "/World/Table")
table.CreateSizeAttr(1.0)
xf = UsdGeom.XformCommonAPI(table)
xf.SetTranslate((0.0, 0.0, -0.02))
xf.SetScale((0.9, 0.9, 0.04))
table.CreateDisplayColorAttr([Gf.Vec3f(0.10, 0.17, 0.12)])

# blocks: the towers in blockworld.json are listed top to bottom; the middle tower is at y = 0
UsdGeom.Xform.Define(stage, "/World/Blocks")
placed = {}
for i, tower in enumerate(DATA["towers"]):
    y = (i - 1) * TOWER_SPACING
    for j, letter in enumerate(reversed(tower)):          # j = 0 is the block on the table
        z = j * EDGE + EDGE / 2
        mesh = block_mesh(f"/World/Blocks/{letter}", EDGE)
        UsdGeom.XformCommonAPI(mesh).SetTranslate((0.0, y, z))
        UsdShade.MaterialBindingAPI(mesh).Bind(letter_material(letter))
        placed[letter] = (0.0, y, z)

# light and camera (the camera looks from +x, so the towers read left to right as in Fig. 1)
UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(350)
sun = UsdLux.DistantLight.Define(stage, "/World/Sun")
sun.CreateIntensityAttr(1400)
UsdGeom.XformCommonAPI(sun).SetRotate((-50.0, 0.0, 60.0))
cam = UsdGeom.Camera.Define(stage, "/World/Camera")
eye, target = Gf.Vec3d(0.62, 0.0, 0.34), Gf.Vec3d(0.0, 0.0, 0.09)
cam.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(eye, target, Gf.Vec3d(0, 0, 1)).GetInverse())
from omni.kit.viewport.utility import get_active_viewport
get_active_viewport().camera_path = "/World/Camera"

print("built", len(placed), "blocks:", ", ".join(f"{k}@z={v[2]:.3f}" for k, v in sorted(placed.items())))
