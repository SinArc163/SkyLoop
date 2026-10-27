# -*- coding: utf-8 -*-
# FINAL track build (v5): elevated oval ring, spawn-only edits (those persist reliably in WP/OFPA).
# PlayerStart is left at its template spot; a ground access road leads up to the ring.
import unreal, math, json, traceback, os, time

MAP = "/Game/VehicleTemplate/Maps/Lvl_VehicleBasic"
A, B = 4400.0, 3800.0
CHORD = 900.0
TRACK_Z = 350.0
TAG = "SkyLoop"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_result.json")

res = {"phase": "start", "errors": [], "counts": {}}

def note(msg):
    unreal.log_warning("SR: " + str(msg))

def try_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        res["errors"].append("%s: %s" % (getattr(fn, "__name__", fn), e))
        return None

def flush():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

try:
    res["phase"] = "get_world"
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    wname = str(world.get_path_name()) if world else "None"
    note("world: %s" % wname)
    if "Lvl_VehicleBasic" not in wname:
        les.load_level(MAP)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        note("load_level fallback -> %s" % world.get_path_name())

    # wait until actor count is stable (WP streaming)
    res["phase"] = "wait_streaming"
    prev, stable = -1, 0
    for _ in range(20):
        n = len(actor_sub.get_all_level_actors())
        if n == prev:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        prev = n
        time.sleep(1.5)
    note("actors loaded (stable): %d" % prev)
    res["initial_actors"] = prev

    res["phase"] = "cleanup"
    old = [a for a in actor_sub.get_all_level_actors() if str(a.get_actor_label()).startswith("SR_")]
    for a in old:
        try_call(actor_sub.destroy_actor, a)
    note("removed old SR actors: %d" % len(old))

    def ellipse_point(t):
        return (A * math.cos(t), B * math.sin(t))

    def tangent_yaw(t):
        dx, dy = (-A * math.sin(t), B * math.cos(t))
        return math.degrees(math.atan2(dy, dx))

    def radial_yaw(t):
        return math.degrees(math.atan2(math.sin(t), math.cos(t)))

    def spawn(cls, loc, yaw=0.0, label=""):
        a = try_call(actor_sub.spawn_actor_from_class, cls,
                     unreal.Vector(loc[0], loc[1], loc[2]), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        if a is None:
            return None
        try_call(a.set_actor_label, label)
        try_call(a.set_folder_path, "SkyLoop")
        try:
            a.tags = [TAG]
        except Exception:
            pass
        return a

    def spawn_mesh(mesh, loc, yaw, scale, label, pitch=0.0):
        a = spawn(unreal.StaticMeshActor, loc, yaw, label)
        if a is None:
            return None
        try_call(a.set_actor_scale3d, unreal.Vector(scale[0], scale[1], scale[2]))
        if pitch:
            try_call(a.set_actor_rotation, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), False)
        comp = a.static_mesh_component
        try_call(comp.set_static_mesh, mesh)
        try_call(comp.set_editor_property, "mobility", unreal.ComponentMobility.STATIC)
        return a

    def spawn_text(text, loc, yaw, size, rgb, label):
        a = spawn(unreal.TextRenderActor, loc, yaw, label)
        if a is None:
            return None
        comp = try_call(a.get_component_by_class, unreal.TextRenderComponent)
        if comp:
            try_call(comp.set_editor_property, "text", unreal.Text(text))
            try_call(comp.set_world_size, size)
            try_call(comp.set_text_render_color, unreal.Color(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), 255))
        return a

    res["phase"] = "assets"
    track_mesh = unreal.load_asset("/Game/VehicleTemplate/Meshes/SM_Track_10M")
    cone_mesh = unreal.load_asset("/Game/VehicleTemplate/Meshes/SM_Cone")
    cube_mesh = unreal.load_asset("/Engine/BasicShapes/Cube")
    if track_mesh is None:
        raise Exception("SM_Track_10M not found")
    tile_w = track_mesh.get_bounds().box_extent.y * 2.0
    note("tile width: %.0f" % tile_w)

    res["phase"] = "segments"
    segs = []
    t = 0.0
    total = 0.0
    while total < 2 * math.pi:
        segs.append([ellipse_point(t)[0], ellipse_point(t)[1], t])
        dx, dy = (-A * math.sin(t), B * math.cos(t))
        step = CHORD / max(1.0, math.hypot(dx, dy))
        t += step
        total += step
    note("segments=%d" % len(segs))
    res["counts"]["segments"] = len(segs)

    res["phase"] = "lay_track"
    fail = 0
    for i, (x, y, tt) in enumerate(segs):
        a = spawn_mesh(track_mesh, (x, y, TRACK_Z), tangent_yaw(tt), (1, 1, 1), "SR_Track_%03d" % i)
        if a is None:
            fail += 1
    res["counts"]["track_tiles"] = len(segs) - fail

    def near_window(tt, centers, width=0.16):
        for c in centers:
            d = abs((tt - c + math.pi) % (2 * math.pi) - math.pi)
            if d < width:
                return True
        return False

    RAMP_THETAS = (math.pi / 2, 3 * math.pi / 2)   # north & south
    ACCESS_THETAS = (0.0,)                          # east, next to template spawn
    windows = tuple(RAMP_THETAS) + ACCESS_THETAS

    wall_n = 0
    for i, (x, y, tt) in enumerate(segs):
        yaw = tangent_yaw(tt)
        px_, py_ = math.sin(math.radians(yaw)), -math.cos(math.radians(yaw))
        for s in (1, -1):  # s=+1 -> outer side
            if s > 0 and near_window(tt, windows):
                continue
            spawn_mesh(cube_mesh, (x + px_ * (tile_w / 2.0 - 25.0) * s, y + py_ * (tile_w / 2.0 - 25.0) * s, TRACK_Z + 40.0),
                       yaw, (9.0, 0.3, 0.8), "SR_Wall_%03d_%d" % (i, s))
            wall_n += 1
    res["counts"]["walls"] = wall_n

    pil = 0
    for i, (x, y, tt) in enumerate(segs):
        if i % 2:
            continue
        yaw = tangent_yaw(tt)
        px_, py_ = math.sin(math.radians(yaw)), -math.cos(math.radians(yaw))
        for s in (1, -1):
            spawn_mesh(cube_mesh, (x + px_ * (tile_w / 2.0 - 60.0) * s, y + py_ * (tile_w / 2.0 - 60.0) * s, 125.0),
                       yaw, (0.6, 0.6, 4.5), "SR_PillarT_%03d_%d" % (i, s))
            pil += 1
    res["counts"]["support_pillars"] = pil

    res["phase"] = "gantry"
    sx, sy = ellipse_point(0.0)
    yaw0 = tangent_yaw(0.0)
    off = tile_w / 2.0 - 100.0   # pillars stand ON the track, clear lane in the middle
    px0, py0 = math.sin(math.radians(yaw0)), -math.cos(math.radians(yaw0))
    for s, lbl in ((1, "SR_Pillar_L"), (-1, "SR_Pillar_R")):
        spawn_mesh(cube_mesh, (sx + px0 * off * s, sy + py0 * off * s, TRACK_Z + 400.0), yaw0, (1.2, 1.2, 8.0), lbl)
    spawn_mesh(cube_mesh, (sx, sy, TRACK_Z + 790.0), yaw0, (2.0 * off / 100.0 + 2, 1.0, 1.0), "SR_StartBeam")
    spawn_mesh(cube_mesh, (sx, sy, TRACK_Z + 14.0), yaw0, (0.4, tile_w / 100.0, 0.06), "SR_StartLine")
    spawn_text("SKYLOOP  START · FINISH", (sx, sy, TRACK_Z + 700.0), yaw0, 70, (1.0, 0.85, 0.0), "SR_Text_Start")

    res["phase"] = "gates"
    for k, tt in enumerate((math.pi / 2, math.pi, 3 * math.pi / 2)):
        gx, gy = ellipse_point(tt)
        gyaw = tangent_yaw(tt)
        px_, py_ = math.sin(math.radians(gyaw)), -math.cos(math.radians(gyaw))
        for s in (1, -1):
            spawn_mesh(cube_mesh, (gx + px_ * off * s, gy + py_ * off * s, TRACK_Z + 350.0), gyaw,
                       (1.0, 1.0, 7.0), "SR_Gate%d_P%d" % (k + 1, s))
            spawn_mesh(cone_mesh, (gx + px_ * (off - 80.0) * s, gy + py_ * (off - 80.0) * s, TRACK_Z + 87.0), gyaw,
                       (1.5, 1.5, 1.5), "SR_Gate%d_Cone%d" % (k + 1, s))
        spawn_mesh(cube_mesh, (gx, gy, TRACK_Z + 690.0), gyaw, (2.0 * off / 100.0 + 1.5, 0.8, 0.8), "SR_Gate%d_Beam" % (k + 1))
        spawn_text("CHECKPOINT CP%d" % (k + 1), (gx, gy, TRACK_Z + 620.0), gyaw, 55, (0.2, 0.9, 1.0), "SR_Text_CP%d" % (k + 1))

    res["phase"] = "ramps"
    L = 1900.0
    drop = TRACK_Z + 100.0
    pitch = -math.degrees(math.atan2(drop, math.sqrt(L * L - drop * drop)))
    for tt, lbl in ((math.pi / 2, "SR_Ramp_N"), (3 * math.pi / 2, "SR_Ramp_S")):
        rx, ry = ellipse_point(tt)
        ryaw = radial_yaw(tt)
        ux, uy = math.cos(math.radians(ryaw)), math.sin(math.radians(ryaw))
        ex = rx + ux * (tile_w / 2.0 - 30.0)
        ey = ry + uy * (tile_w / 2.0 - 30.0)
        spawn_mesh(cube_mesh, (ex + ux * (L / 2.0), ey + uy * (L / 2.0), (TRACK_Z - 100.0) / 2.0 + 25.0),
                   ryaw, (L / 100.0, 3.5, 0.5), lbl, pitch=pitch)
    res["counts"]["ramps"] = 2

    res["phase"] = "access"
    # one climb ramp: ground (~z120) up to track edge z350 over 13m, plus signs
    acc_len = 1300.0
    acc_pitch = -math.degrees(math.atan2(230.0, acc_len))
    spawn_mesh(cube_mesh, (5597.0, 0.0, 187.0), 0.0, (acc_len / 100.0, 3.5, 0.5), "SR_Access_Ramp", pitch=acc_pitch)
    spawn_text("TRACK ENTRANCE - EAST", (4450.0, 900.0, 260.0), 270.0, 60, (0.4, 1.0, 0.4), "SR_Text_Spawn")
    spawn_text("ENTRANCE AHEAD", (5000.0, 0.0, 480.0), 180.0, 60, (0.4, 1.0, 0.4), "SR_Text_Access")
    res["counts"]["access"] = 1

    res["phase"] = "board"
    bx = sx + 1400.0
    spawn_text("SKYLOOP TIMING", (bx, sy, TRACK_Z + 550.0), 180.0, 150, (1.0, 1.0, 0.2), "SR_Board")
    spawn_text("W/S throttle-brake  A/D steer  Space handbrake  R reset", (bx, sy, TRACK_Z + 290.0), 180.0, 60, (1.0, 1.0, 1.0), "SR_Text_Help")

    res["phase"] = "save"
    ok = try_call(unreal.EditorLoadingAndSavingUtils.save_dirty_packages, True, True)
    try_call(les.save_current_level)
    res["saved"] = bool(ok)

    res["phase"] = "post_verify"
    sr = [a for a in actor_sub.get_all_level_actors() if str(a.get_actor_label()).startswith("SR_")]
    res["counts"]["total_sr_in_memory"] = len(sr)
    ps = [a for a in actor_sub.get_all_level_actors() if a.get_class().get_name() == "PlayerStart"]
    if ps:
        p = ps[0].get_actor_location()
        res["player_start_after"] = [round(p.x, 1), round(p.y, 1), round(p.z, 1)]
    res["phase"] = "done"
    note("TRACK_BUILD_DONE saved=%s counts=%s errors=%d" % (ok, res["counts"], len(res["errors"])))
except Exception:
    res["fatal"] = traceback.format_exc()
    note("TRACK_BUILD_FATAL")
    note(res["fatal"])
finally:
    flush()
