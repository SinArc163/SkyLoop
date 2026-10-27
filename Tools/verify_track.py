# -*- coding: utf-8 -*-
# Verify persisted track actors in a fresh load of the map.
import unreal, json, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_result.json")
res = {}

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
les.load_level("/Game/VehicleTemplate/Maps/Lvl_VehicleBasic")
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_sub.get_all_level_actors()

sr = [a for a in actors if str(a.get_actor_label()).startswith("SR_")]
res["total_actors"] = len(actors)
res["sr_actors"] = len(sr)
res["labels"] = sorted(str(a.get_actor_label()) for a in sr)

for a in actors:
    lbl = str(a.get_actor_label())
    if lbl.startswith("SR_Ramp"):
        res[lbl] = {"loc": [round(v, 1) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)],
                    "rot": [round(getattr(a.get_actor_rotation(), k), 1) for k in ("pitch", "yaw", "roll")]}
    if a.get_class().get_name() == "PlayerStart":
        res["player_start"] = {"loc": [round(v, 1) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)],
                               "rot": [round(getattr(a.get_actor_rotation(), k), 1) for k in ("pitch", "yaw", "roll")]}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
unreal.log_warning("SR: VERIFY_DONE sr=%d total=%d" % (res["sr_actors"], res["total_actors"]))
