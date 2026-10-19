"""Generate offline FTE brush-precache regressions without captured server data.

Usage: python3 Misc/make_fte_precache_demos.py OUTPUT_DIRECTORY
Play the generated demos with registered Quake PAKs, +r_novis 1 and +playdemo.
Each demo prints its case name after the tested messages have been parsed.
The dynamic replacement deliberately has no subsequent entity snapshot.
"""

import argparse
from pathlib import Path
import struct


def string(value):
    return value.encode("ascii") + b"\0"


def precache(index, name):
    return b"\x36" + struct.pack("<H", index) + string(name)


def clock(time):
    # svc_time includes an input sequence acknowledgement with PEXT2_PREDINFO.
    return b"\x07" + struct.pack("<fH", time, 0)


def entity(number, model, origin):
    # UF_EXTEND1 | UF_ORIGINXY | UF_ORIGINZ, UF_RESET | UF_MODEL.
    return struct.pack("<HBBhhhB", number, 0x86, 0x05,
                       *(int(v * 8) for v in origin), model)


def snapshot(time, entities=b""):
    return b"\x56" + struct.pack("<Hf", 0, time) + entities + b"\0\0"


def static(model):
    result = bytes([20, model, 0, 0, 0])
    for coordinate in (2344, -1320, 0):
        result += struct.pack("<hB", coordinate * 8, 0)
    return result


def signon():
    info = (b"\x0bFTE2" + struct.pack("<II", 0x28, 666) + b"\0\x01\x01"
            + string("FTE precache regression") + string("maps/dm2.bsp")
            + b"\0\0")
    resources = (precache(2, "maps/b_shell1.bsp")
                 + precache(3, "progs/player.mdl") + b"\x0c\0m\0")
    stages = b"\x19\x01\x19\x02\x19\x03\x05\x01\0"
    entities = (b"\0\x80"  # reset the entity snapshot, including world
                + entity(1, 3, (2280, -1320, 24)))
    return [info, resources + stages, snapshot(1, entities)]


def write_demo(path, messages):
    path.write_bytes(b"-1\n" + b"".join(
        struct.pack("<i3f", len(message), 0, 0, 0) + message
        for message in messages))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    small, large = "maps/b_shell0.bsp", "maps/b_shell1.bsp"
    cases = {
        "signon": [],
        "late": [clock(1.1) + precache(4, small) + static(4)],
        "sparse": [clock(1.1) + precache(96, small) + static(96)],
        "duplicate": [clock(1.1) + precache(4, small) + precache(5, small) + static(5)],
        "static-first": [clock(1.1) + static(4) + precache(4, small)],
        "static-replaced": [clock(1.1) + static(2), clock(1.2) + precache(2, small)],
        "repeated": [clock(1.1) + static(2)] + [
            clock(1.2 + i * 0.1) + precache(2, small if i % 2 == 0 else large)
            for i in range(12)],
        "dynamic-replaced": [
            # Replace after resolving the entity, within the same message. Its
            # future timestamp keeps it live without another snapshot.
            snapshot(60, entity(2, 2, (2344, -1320, 0))) + precache(2, small)],
        "legacy-dynamic-replaced": [
            clock(60) + bytes([0x8f, 0x04, 2, 2])
            + struct.pack("<hhh", 2344 * 8, -1320 * 8, 0) + precache(2, small)],
        "world-replaced": [clock(1.1) + precache(1, "maps/dm1.bsp")],
    }
    for name, updates in cases.items():
        messages = signon() + updates
        messages.append(b"\x08" + string("precache-case: " + name + "\n"))
        # Freeze server time after the operation so references stay live. The
        # final future packet keeps playback/rendering running for a bounded test.
        messages.append(clock(120))
        path = args.output_directory / ("precache-" + name + ".dem")
        write_demo(path, messages)
        print(path)


if __name__ == "__main__":
    main()
