import bpy
import traceback

try:
    bpy.ops.preferences.addon_install(filepath=r"D:\Tripo3d_Blender_Bridge-latest.zip")
    print("INSTALL_OK")
except Exception:
    traceback.print_exc()

try:
    bpy.ops.preferences.addon_enable(module="Tripo3d_Blender_Bridge")
    print("ENABLE_OK")
    print("ADDONS", [a.module for a in bpy.context.preferences.addons if "Tripo" in a.module])
except Exception:
    traceback.print_exc()
