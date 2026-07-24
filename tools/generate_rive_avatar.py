"""
Generate a minimal valid Rive .riv file for May's Rive Avatar.

This script creates a .riv file with:
- An Artboard containing a circle (Ellipse + Fill + SolidColor)
- DrawRules for render ordering
- A StateMachine with May's required inputs:
  - Boolean: isThinking, isListening, isSpeaking
  - Number: mood (0-4), amplitude (0.0-1.0)

Usage: python tools/generate_rive_avatar.py

Output: public/avatar.riv

Based on Rive file format v7 (https://rive.app/docs/runtimes/advanced-topic/format)
and type IDs from rive-runtime source (github.com/rive-app/rive-runtime).

Encoding notes:
- CoreUintType and CoreColorType serialize as 4-byte LE uint32
- CoreDoubleType serializes as 4-byte LE float32
- CoreBoolType serializes as 4-byte LE uint32 (0 or 1)
- CoreStringType serializes as varuint length + UTF-8
"""

import struct
import io
from pathlib import Path

# ── LEB128 encoding ────────────────────────────────────────────────────────

def write_varuint(value: int) -> bytes:
    """Encode unsigned integer as LEB128."""
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            break
    return bytes(result)


def write_string(value: str) -> bytes:
    """Encode string as varuint length + UTF-8 bytes."""
    utf8 = value.encode("utf-8")
    return write_varuint(len(utf8)) + utf8


# ── Rive core type IDs (from rive-runtime generated headers) ─────────────

TYPE_ARTBOARD = 1
TYPE_SHAPE = 3
TYPE_ELLIPSE = 4
TYPE_SOLID_COLOR = 18
TYPE_FILL = 20
TYPE_DRAW_RULES = 49
TYPE_STATE_MACHINE = 53
TYPE_SM_INPUT = 55
TYPE_SM_NUMBER = 56
TYPE_SM_LAYER = 57
TYPE_SM_BOOL = 59
TYPE_LAYER_STATE = 60
TYPE_ANIMATION_STATE = 61
TYPE_ANY_STATE = 62
TYPE_ENTRY_STATE = 63
TYPE_STATE_TRANSITION = 65

# ── Property IDs (from rive-runtime generated headers) ───────────────────

# Component (type 10): name=4(string), parentId=5(uint32)
PROP_NAME = 4
PROP_PARENT_ID = 5

# Node (type 2): x=13(float), y=14(float)
PROP_X = 13
PROP_Y = 14

# TransformComponent (type 38): rotation=15(float), scaleX=16(float), scaleY=17(float)
PROP_SCALE_X = 16
PROP_SCALE_Y = 17

# Artboard (type 1): originX=11(float), originY=12(float),
#                    defaultStateMachineId=236(uint32)
PROP_ORIGIN_X = 11
PROP_ORIGIN_Y = 12
PROP_DEFAULT_SM = 236

# Animation base (type 27): name=55(string)
PROP_ANIM_NAME = 55

# SolidColor (type 18): colorValue=37(color=uint32 ARGB)
PROP_COLOR_VALUE = 37

# Fill (type 20): fillRule=40(uint32)
PROP_FILL_RULE = 40

# ShapePaint (type 21): isVisible=41(bool)
PROP_IS_VISIBLE = 41

# DrawRules (type 49): drawTargetId=121(uint32)
PROP_DRAW_TARGET_ID = 121

# StateMachineComponent (type 54): name=138(string)
PROP_SM_NAME = 138

# StateMachineBool (type 59): value=141(bool)
PROP_BOOL_VALUE = 141

# StateMachineNumber (type 56): value=140(float)
PROP_NUMBER_VALUE = 140

# StateTransition (type 65): stateToId=151(uint32), flags=152(uint32),
#                            duration=158(uint32)
PROP_STATE_TO_ID = 151
PROP_TRANS_FLAGS = 152
PROP_TRANS_DURATION = 158

# AnimationState (type 61): animationId=149(uint32)
PROP_ANIMATION_ID = 149

# LayerState (type 60): flags=536(uint32)
PROP_LAYER_FLAGS = 536


# ── Property backing types (for ToC) ──────────────────────────────────────
BACKING_UINT = 0
BACKING_STRING = 1
BACKING_FLOAT = 2
BACKING_COLOR = 3


class RiveWriter:
    """Writes a minimal valid Rive .riv file."""
    
    def __init__(self):
        self.buf = io.BytesIO()
        self.property_keys: dict[int, int] = {}
    
    def register(self, key: int, backing: int):
        self.property_keys[key] = backing
    
    def write_header(self):
        """Write the Rive file header per v7 format spec."""
        self.buf.write(b"RIVE")                        # magic
        self.buf.write(write_varuint(7))                 # major version
        self.buf.write(write_varuint(0))                 # minor version
        self.buf.write(write_varuint(0))                 # file ID
        
        # ToC: property keys list terminated by 0
        for key in sorted(self.property_keys):
            self.buf.write(write_varuint(key))
        self.buf.write(write_varuint(0))
        
        # Bit array: 2 bits per property key for backing type
        n = len(self.property_keys)
        num_bytes = max(1, (n * 2 + 7) // 8)
        bits = bytearray(num_bytes)
        for i, key in enumerate(sorted(self.property_keys)):
            bt = self.property_keys[key] & 3
            idx = (i * 2) // 8
            off = (i * 2) % 8
            bits[idx] |= bt << off
        self.buf.write(bytes(bits))
    
    def obj(self, type_id: int, props: list[tuple[int, bytes]]):
        """Write a Rive object: typeKey(varuint) + props(key+value...) + terminator(0)."""
        self.buf.write(write_varuint(type_id))
        for key, val in props:
            self.buf.write(write_varuint(key))
            self.buf.write(val)
        self.buf.write(write_varuint(0))
    
    def f32(self, v: float) -> bytes:
        return struct.pack("<f", v)
    
    def u32(self, v: int) -> bytes:
        return struct.pack("<I", v)
    
    def bl(self, v: bool) -> bytes:
        return struct.pack("<I", 1 if v else 0)
    
    def clr(self, r: int, g: int, b: int, a: int = 255) -> bytes:
        return struct.pack("<I", (a << 24) | (r << 16) | (g << 8) | b)
    
    def bytes(self) -> bytes:
        return self.buf.getvalue()


def go(output_path: str):
    w = RiveWriter()
    
    # ── Register all property keys used in this file ──────────────────
    for k, bt in [
        (PROP_PARENT_ID,   BACKING_UINT),
        (PROP_NAME,        BACKING_STRING),
        (PROP_X,           BACKING_FLOAT),
        (PROP_Y,           BACKING_FLOAT),
        (PROP_SCALE_X,     BACKING_FLOAT),
        (PROP_SCALE_Y,     BACKING_FLOAT),
        (PROP_ORIGIN_X,    BACKING_FLOAT),
        (PROP_ORIGIN_Y,    BACKING_FLOAT),
        (PROP_DEFAULT_SM,  BACKING_UINT),
        (PROP_ANIM_NAME,   BACKING_STRING),
        (PROP_COLOR_VALUE, BACKING_COLOR),
        (PROP_FILL_RULE,   BACKING_UINT),
        (PROP_IS_VISIBLE,  BACKING_UINT),
        (PROP_DRAW_TARGET_ID, BACKING_UINT),
        (PROP_SM_NAME,     BACKING_STRING),
        (PROP_BOOL_VALUE,  BACKING_UINT),
        (PROP_NUMBER_VALUE,BACKING_FLOAT),
        (PROP_STATE_TO_ID, BACKING_UINT),
        (PROP_TRANS_FLAGS, BACKING_UINT),
        (PROP_TRANS_DURATION, BACKING_UINT),
        (PROP_ANIMATION_ID, BACKING_UINT),
        (PROP_LAYER_FLAGS, BACKING_UINT),
    ]:
        w.register(k, bt)
    
    w.write_header()
    
    # ── Object indices (for parentId within Artboard) ─────────────────
    # Each Artboard child gets an index: 0, 1, 2, etc. in order of appearance
    IDX_SHAPE = 0
    IDX_ELLIPSE = 1
    IDX_FILL = 2
    IDX_SOLID_COLOR = 3
    IDX_DRAW_RULES = 4
    IDX_STATE_MACHINE = 5
    
    # ── 1. Artboard (type 1) ──────────────────────────────────────────
    w.obj(TYPE_ARTBOARD, [
        (PROP_NAME,        write_string("MayAvatar")),
        (PROP_ORIGIN_X,    w.f32(100.0)),
        (PROP_ORIGIN_Y,    w.f32(100.0)),
        (PROP_DEFAULT_SM,  w.u32(0)),  # first animation = StateMachine
    ])
    
    # ── 2. Shape (type 3) — container for geometry + paint ────────────
    # parentId = Artboard itself is not in the child index list, so parentId=0
    # means root (Artboard). But Artboard children use indices within the
    # Artboard. For a child of the Artboard itself, we omit parentId.
    w.obj(TYPE_SHAPE, [
        (PROP_X, w.f32(100.0)),
        (PROP_Y, w.f32(100.0)),
    ])
    
    # ── 3. Ellipse (type 4) — the circular path geometry ──────────────
    # parentId = Shape (index 0 in Artboard's children)
    # scaleX=scaleY=50 makes the ellipse 100x100 units at default
    w.obj(TYPE_ELLIPSE, [
        (PROP_PARENT_ID, w.u32(IDX_SHAPE)),
        (PROP_X,         w.f32(0.0)),
        (PROP_Y,         w.f32(0.0)),
        (PROP_SCALE_X,   w.f32(50.0)),
        (PROP_SCALE_Y,   w.f32(50.0)),
    ])
    
    # ── 4. Fill (type 20) — color fill for the Shape ──────────────────
    # parentId = Shape (index 0)
    w.obj(TYPE_FILL, [
        (PROP_PARENT_ID,  w.u32(IDX_SHAPE)),
        (PROP_IS_VISIBLE, w.bl(True)),
        (PROP_FILL_RULE,  w.u32(0)),
    ])
    
    # ── 5. SolidColor (type 18) — the actual color ────────────────────
    # parentId = Fill (index 2)
    # Color: cyan #06B6D4
    w.obj(TYPE_SOLID_COLOR, [
        (PROP_PARENT_ID, w.u32(IDX_FILL)),
        (PROP_COLOR_VALUE, w.clr(0x06, 0xB6, 0xD4)),
    ])
    
    # ── 6. DrawRules (type 49) — ensures the Shape is rendered ────────
    # drawTargetId points to the Shape (index 0 in Artboard's children)
    w.obj(TYPE_DRAW_RULES, [
        (PROP_DRAW_TARGET_ID, w.u32(IDX_SHAPE)),
    ])
    
    # ── 7. StateMachine (type 53) ─────────────────────────────────────
    w.obj(TYPE_STATE_MACHINE, [
        (PROP_ANIM_NAME, write_string("MayStateMachine")),
    ])
    
    # ── 8. StateMachineLayer (type 57) ────────────────────────────────
    w.obj(TYPE_SM_LAYER, [
        (PROP_SM_NAME, write_string("Main Layer")),
    ])
    
    # ── 9. EntryState (type 63) ───────────────────────────────────────
    w.obj(TYPE_ENTRY_STATE, [])
    
    # ── 10. AnyState (type 62) ────────────────────────────────────────
    w.obj(TYPE_ANY_STATE, [
        (PROP_LAYER_FLAGS, w.u32(0)),
    ])
    
    # ── 11. StateTransition Entry -> AnyState (type 65) ──────────────
    # stateToId = 1 (0=EntryState, 1=AnyState)
    w.obj(TYPE_STATE_TRANSITION, [
        (PROP_STATE_TO_ID,   w.u32(1)),
        (PROP_TRANS_FLAGS,   w.u32(0)),
        (PROP_TRANS_DURATION, w.u32(0)),
    ])
    
    # ── 12-14. Boolean inputs (type 59) ───────────────────────────────
    w.obj(TYPE_SM_BOOL, [
        (PROP_SM_NAME,    write_string("isThinking")),
        (PROP_BOOL_VALUE, w.bl(False)),
    ])
    w.obj(TYPE_SM_BOOL, [
        (PROP_SM_NAME,    write_string("isListening")),
        (PROP_BOOL_VALUE, w.bl(False)),
    ])
    w.obj(TYPE_SM_BOOL, [
        (PROP_SM_NAME,    write_string("isSpeaking")),
        (PROP_BOOL_VALUE, w.bl(False)),
    ])
    
    # ── 15-16. Number inputs (type 56) ────────────────────────────────
    w.obj(TYPE_SM_NUMBER, [
        (PROP_SM_NAME,     write_string("mood")),
        (PROP_NUMBER_VALUE, w.f32(0.0)),
    ])
    w.obj(TYPE_SM_NUMBER, [
        (PROP_SM_NAME,     write_string("amplitude")),
        (PROP_NUMBER_VALUE, w.f32(0.0)),
    ])
    
    # ── Write output ──────────────────────────────────────────────────
    data = w.bytes()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    
    print(f"[OK] Generated {out}")
    print(f"     Size: {len(data)} bytes | {len(w.property_keys)} property keys | 16 objects")
    print(f"     State Machine: MayStateMachine")
    print(f"       Boolean: isThinking, isListening, isSpeaking")
    print(f"       Number:  mood, amplitude")
    print()
    print("[NOTE] Minimal .riv file — for full animation capabilities,")
    print("       create the .riv in the Rive Editor (rive.app) following")
    print("       docs/RIVE_CREATION_GUIDE.md")
    print("       RiveAvatar falls back to SVG if loading fails.")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    go(str(root / "public" / "avatar.riv"))
