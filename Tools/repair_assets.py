# -*- coding: utf-8 -*-
# Repair pass: replace the broken template touch-UI widget, force-load everything,
# recompile all blueprints, save, and report.
import unreal, json, traceback, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repair_result.json")
res = {"errors": [], "referencers": [], "steps": []}

def note(m):
    unreal.log_warning("FIX: " + str(m))

def try_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        res["errors"].append("%s: %s" % (getattr(fn, "__name__", fn), e))
        return None

try:
    ar = unreal.get_editor_subsystem(unreal.AssetRegistrySubsystem if hasattr(unreal, "AssetRegistrySubsystem") else unreal.EditorAssetSubsystem)
    # asset registry
    reg = unreal.AssetRegistryHelpers.get_asset_registry()

    TOUCH = "/Game/VehicleTemplate/Input/UI_Touch_Vehicle"
    touch_id = try_call(reg.get_asset_by_object_path, TOUCH + ".UI_Touch_Vehicle_C") or try_call(reg.get_asset_by_object_path, TOUCH)
    if touch_id:
        refs = try_call(reg.get_referencers, touch_id.package_name, unreal.Name(), unreal.AssetRegistryDependencyOptions())
        res["referencers"] = [str(r) for r in (refs or [])]
        note("touch widget referencers: %s" % res["referencers"])

    # 1) delete broken widget
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    deleted = try_call(eas.delete_asset, TOUCH)
    res["steps"].append("delete_broken_widget=%s" % deleted)
    note("deleted broken widget: %s" % deleted)

    # 2) recreate blank widget at the same path
    at = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.WidgetBlueprintFactory()
    new_bp = try_call(at.create_asset, "UI_Touch_Vehicle", "/Game/VehicleTemplate/Input",
                      unreal.WidgetBlueprint, factory)
    res["steps"].append("create_blank_widget=%s" % (new_bp is not None))
    note("created blank widget: %s" % new_bp)
    if new_bp:
        try_call(unreal.EditorAssetLibrary.save_asset, TOUCH)

    # 3) list all project assets and load them
    assets = [a for a in reg.get_assets_by_path("/Game", True)]
    res["total_assets"] = len(assets)
    note("project assets: %d" % len(assets))
    loaded = 0
    for a in assets:
        p = str(a.package_name)
        obj = try_call(unreal.EditorAssetLibrary.load_asset, p)
        if obj is not None:
            loaded += 1
    res["loaded_assets"] = loaded
    note("loaded ok: %d" % loaded)

    # 4) recompile every blueprint
    bps = [a for a in assets if str(a.asset_class_path.asset_name).endswith("_C") or str(a.asset_class_path.asset_name) == "Blueprint"]
    compiled = []
    for a in assets:
        cls = str(a.asset_class_path.asset_name)
        if cls in ("Blueprint", "WidgetBlueprint", "AnimationBlueprint"):
            p = str(a.package_name)
            bp = unreal.EditorAssetLibrary.load_asset(p)
            if bp is None:
                continue
            ok = try_call(unreal.BlueprintEditorLibrary.compile_blueprint, bp)
            compiled.append((p, bool(ok)))
    res["compiled"] = [p for p, ok in compiled if ok]
    res["compile_failed"] = [p for p, ok in compiled if not ok]
    note("compiled %d blueprints, failed: %s" % (len(res["compiled"]), res["compile_failed"]))

    # 5) save everything dirty
    ok = try_call(unreal.EditorLoadingAndSavingUtils.save_dirty_packages, True, True)
    res["saved"] = bool(ok)
    note("REPAIR_DONE saved=%s" % ok)
except Exception:
    res["fatal"] = traceback.format_exc()
    note("REPAIR_FATAL")
    note(res["fatal"])
finally:
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
