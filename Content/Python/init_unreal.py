# -*- coding: utf-8 -*-
# SkyLoop lap-timing HUD.
# Auto-loaded by the editor at startup (Content/Python/init_unreal.py).
# While PIE runs, a slate post-tick callback tracks the player car around the
# elevated oval (A=4400, B=3800) and draws lap / time / speed via PrintString.

import unreal
import math
import time

TRACK_A = 4400.0
TRACK_B = 3800.0
TWO_PI = 2.0 * math.pi

_st = {
    "handle": None,
    "acc": 0.0,          # unwrapped angular progress (radians, positive = race direction)
    "laps_done": 0,
    "lap_start": None,   # time.monotonic() of current lap start
    "best": None,
    "last": None,
    "prev_theta": None,
    "err_count": 0,
}


def _car_theta(x, y):
    # ellipse parameter angle that matches the built ring
    return math.atan2(y / TRACK_B, x / TRACK_A)


def _hud_tick(delta_seconds):
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ues.get_game_world() if ues else None
        if world is None:
            return
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        if pawn is None:
            return
        loc = pawn.get_actor_location()
        x, y = loc.x, loc.y

        theta = _car_theta(x, y)
        r = math.hypot(x / TRACK_A, y / TRACK_B)
        prev = _st["prev_theta"]
        _st["prev_theta"] = theta

        if 0.7 < r < 1.4:
            if prev is not None:
                d = (theta - prev + math.pi) % TWO_PI - math.pi
                if abs(d) < 1.2:            # ignore teleports / resets
                    _st["acc"] += d

        now = time.monotonic()
        if _st["lap_start"] is None:
            _st["lap_start"] = now

        new_laps = int(_st["acc"] / TWO_PI)
        if new_laps > _st["laps_done"]:
            lap_t = now - _st["lap_start"]
            _st["last"] = lap_t
            if _st["best"] is None or lap_t < _st["best"]:
                _st["best"] = lap_t
            _st["laps_done"] = new_laps
            _st["lap_start"] = now
        elif new_laps < _st["laps_done"]:
            _st["laps_done"] = new_laps      # drove backwards over the line

        vel = pawn.get_velocity()
        kmh = math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z) * 0.036

        lap_no = _st["laps_done"] + 1
        lap_t = now - _st["lap_start"]
        pct = (_st["acc"] % TWO_PI) / TWO_PI * 100.0
        best = "%.1f" % _st["best"] if _st["best"] is not None else "--"
        last = "%.1f" % _st["last"] if _st["last"] is not None else "--"

        text = ("SkyLoop  Lap %d   Time %.1f s\n"
                "Speed %.0f km/h    Progress %.0f %%\n"
                "Best %s s    Last %s s") % (lap_no, lap_t, kmh, pct, best, last)

        try:
            unreal.SystemLibrary.print_string(world, text, print_to_screen=True,
                                              print_to_log=False,
                                              text_color=unreal.LinearColor(1.0, 0.85, 0.2, 1.0),
                                              duration=1.0, key="srhud")
        except TypeError:
            unreal.SystemLibrary.print_string(world, text, True, False,
                                              unreal.LinearColor(1.0, 0.85, 0.2, 1.0), 1.0, "srhud")
    except Exception:
        _st["err_count"] += 1
        if _st["err_count"] == 1:
            unreal.log_warning("[SkyLoop] HUD tick error (once):")
            import traceback
            unreal.log_warning(traceback.format_exc())
        if _st["err_count"] > 300:
            if _st["handle"] is not None:
                try:
                    unreal.unregister_slate_post_tick_callback(_st["handle"])
                except Exception:
                    pass
                _st["handle"] = None


def _boot():
    _st["handle"] = unreal.register_slate_post_tick_callback(_hud_tick)
    unreal.log_warning("[SkyLoop] HUD armed: lap timing active during PIE. "
                       "W/S throttle-brake, A/D steer, Space handbrake, R reset.")


_boot()
