"""Human-readable, fail-closed text rendering for #69 reconstructed actions."""
from __future__ import annotations

_TILE_SUIT = {"M": "万", "P": "筒", "S": "条"}
_NUM = {"1":"一","2":"二","3":"三","4":"四","5":"五","6":"六","7":"七","8":"八","9":"九"}
_HONOR = {"E":"东","SOUTH":"南","W":"西","N":"北","R":"中","G":"发","WH":"白"}


def tile_text(tile: str | None) -> str:
    if not tile:
        return "未知牌"
    if len(tile) == 2 and tile[0] in _TILE_SUIT and tile[1] in _NUM:
        return _NUM[tile[1]] + _TILE_SUIT[tile[0]]
    return _HONOR.get(tile, tile)


def render_reconstructed_timeline(report: dict, *, hand_number: int | None = None,
                                  total_hands: int = 8) -> list[str]:
    if report.get("schema_version") != "issue69_temporal_reconstruction_v0_1":
        raise ValueError("unsupported temporal reconstruction report")
    prefix = f"第{hand_number}/{total_hands}局 " if hand_number is not None else ""
    rows = []
    for action in sorted(report.get("actions", ()), key=lambda x: x["timestamp_seconds"]):
        actor = {"player":"我方","opponent":"对手","system":"系统"}.get(action["actor"], "未知方")
        kind = action["kind"]
        if kind == "DISCARD":
            text = f"{actor}打出{tile_text(action.get('tile'))}"
        elif kind in {"CHI","PENG","MING_GANG","ADD_KONG"}:
            name = {"CHI":"吃","PENG":"碰","MING_GANG":"明杠","ADD_KONG":"补杠"}[kind]
            meld = " ".join(tile_text(tile) for tile in action.get("meld", ()))
            text = f"{actor}{name}" + (f"（{meld}）" if meld else "")
        elif kind == "UNKNOWN_ACTION":
            reasons = ",".join(action.get("unknown_reasons", ())) or "证据不足"
            text = f"{actor}未确认动作（{reasons}）"
        elif kind == "EVIDENCE_CONFLICT":
            text = f"{actor}证据冲突"
        else:
            text = f"{actor}{kind}"
        rows.append(f"{prefix}{action['timestamp_seconds']:.2f}s {text}")
        prefix = ""
    return rows
