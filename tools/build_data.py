#!/usr/bin/env python3
# -*- coding: cp1252 -*-
"""
Builds data/cards.json from a LOCAL copy of the GameFAQs
Yu-Gi-Oh! GX Tag Force 2 Booster Pack FAQ.

Input:
    data/gamefaqs.txt

Output:
    data/cards.json

The GameFAQs website is NOT accessed.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FAQ_FILE = ROOT / "data" / "gamefaqs.txt"
PACKS_FILE = ROOT / "data" / "packs.json"
OUT = ROOT / "data" / "cards.json"


SEPARATOR = "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"


def clean_name(name: str) -> str:
    """
    Cleans known spelling mistakes from the GameFAQs list.

    The original name is preserved in the 'name' field.
    The corrected version is stored in 'lookup'.
    """

    name = name.strip()
    name = re.sub(r"\s+", " ", name)

    aliases = {
        "The Flute fo Summoning Kuriboh":
            "The Flute of Summoning Kuriboh",

        "Toon Cannon Solider":
            "Toon Cannon Soldier",

        "Hade-Hane":
            "Hane-Hane",

        "Mulitiply":
            "Multiply",

        "Relinguished":
            "Relinquished",

        "Wicked-Breaking Flameerge - Baou":
            "Wicked-Breaking Flamberge - Baou",

        "Gearfired the Swordmaster":
            "Gearfried the Swordmaster",

        "Metamorph":
            "Metalmorph",

        "Mask of Resitrict":
            "Mask of Restrict",

        "Spatical Collapse":
            "Spatial Collapse",

        "Cermonial Bell":
            "Ceremonial Bell",

        "Statellite Cannon":
            "Satellite Cannon",

        "Penumbral Solider Lady":
            "Penumbral Soldier Lady",

        "Giant Turle Who Feeds On Flames":
            "Giant Turtle Who Feeds on Flames",

        "Giant Turle Who Feeds on Flames":
            "Giant Turtle Who Feeds on Flames",

        "Return to the Doomed":
            "Return of the Doomed",
    }

    return aliases.get(name, name)


def load_local_faq() -> str:
    if not FAQ_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró:\n{FAQ_FILE}\n\n"
            "Creá data/gamefaqs.txt y pegá ahí el contenido "
            "del FAQ de GameFAQs."
        )

    text = FAQ_FILE.read_text(encoding="utf-8-sig")

    if not text.strip():
        raise RuntimeError("data/gamefaqs.txt está vacío.")

    return text


def parse_card_line(line: str):
    """
    The local FAQ does not number individual cards.

    Therefore we simply treat every non-empty line inside a rarity
    section as a card name.
    """

    line = line.strip()

    if not line:
        return None

    # Ignore obvious metadata.
    if line.startswith("How To Unlock:"):
        return None

    if line == "Cards:":
        return None

    return line


def parse_pack(block: str):
    """
    Parses one pack block.

    Example:

        1. Beginner Monsters
        How To Unlock: Available From Start
        Cards:
        Gold
        Asura Priest
        ...
    """

    lines = [line.strip() for line in block.splitlines()]

    # Remove empty lines.
    lines = [line for line in lines if line]

    if not lines:
        return None

    # First meaningful line must be:
    #
    # 1. Beginner Monsters
    #
    # Some copied text may contain tabs or unusual whitespace.
    match = re.match(r"^(\d{1,2})\.\s*(.+?)\s*$", lines[0])

    if not match:
        return None

    pack_id = int(match.group(1))
    pack_name = match.group(2).strip()

    cards = []

    # Current rarity.
    rarity = None

    rarity_names = {
        "Gold",
        "Silver",
        "Bronze",
        "Normal",
    }

    for line in lines[1:]:

        if line.startswith("How To Unlock:"):
            continue

        if line == "Cards:":
            continue

        if line in rarity_names:
            rarity = line
            continue

        # Special packs 16 and 48.
        if pack_id == 16:
            continue

        if pack_id == 48:
            continue

        card_name = parse_card_line(line)

        if not card_name:
            continue

        # Avoid accidental footer text.
        if card_name.startswith("*Thanks again"):
            continue

        cards.append({
            "name": card_name,
            "lookup": clean_name(card_name),
            "rarity": rarity,
            "number": len(cards) + 1,
        })

    return {
        "id": pack_id,
        "name": pack_name,
        "cards": cards,
    }


def load_pack_metadata():
    """
    If packs.json exists, preserve its image/yugipedia metadata.

    This allows the new local parser to coexist with your existing
    pack images and Yugipedia URLs.
    """

    if not PACKS_FILE.exists():
        print("Aviso: data/packs.json no existe.")
        print("Se generará cards.json sin metadata adicional.")
        return {}

    try:
        data = json.loads(
            PACKS_FILE.read_text(encoding="utf-8")
        )
    except Exception as e:
        print(f"Aviso: no se pudo leer packs.json: {e}")
        return {}

    result = {}

    # Accept either:
    #
    # { "packs": [...] }
    #
    # or:
    #
    # [...]
    #
    if isinstance(data, dict):
        source_packs = data.get("packs", [])
    else:
        source_packs = data

    for pack in source_packs:
        if not isinstance(pack, dict):
            continue

        pack_id = pack.get("id")

        if pack_id is None:
            continue

        result[int(pack_id)] = pack

    return result


def parse():
    text = load_local_faq()

    # The separators make this considerably more reliable than trying
    # to parse the entire document with one giant regular expression.
    blocks = text.split(SEPARATOR)

    packs = []

    for block in blocks:
        pack = parse_pack(block)

        if pack:
            packs.append(pack)

    packs.sort(key=lambda p: p["id"])

    return packs


def build_checkered_flag(packs):
    """
    Pack 48 is defined as containing cards from all other packs.

    We generate it automatically from packs 1-47.
    """

    seen = set()
    all_cards = []

    for pack in packs:
        if pack["id"] == 48:
            continue

        for card in pack["cards"]:

            key = card["lookup"].casefold()

            if key in seen:
                continue

            seen.add(key)

            new_card = dict(card)
            new_card["number"] = len(all_cards) + 1

            all_cards.append(new_card)

    return all_cards


def merge_metadata(packs):
    metadata = load_pack_metadata()

    for pack in packs:
        old = metadata.get(pack["id"])

        if not old:
            continue

        # Preserve existing fields such as:
        #
        # image
        # yugipedia
        # cover
        #
        # without allowing the old empty 'cards' list to overwrite
        # our newly parsed cards.

        for key, value in old.items():

            if key in {
                "cards",
                "id",
                "name",
            }:
                continue

            pack[key] = value


def validate(packs):

    print()
    print("=" * 60)
    print("VALIDACIÓN")
    print("=" * 60)

    print(f"Packs encontrados: {len(packs)}/48")

    if len(packs) != 48:
        found = {p["id"] for p in packs}
        missing = [
            i for i in range(1, 49)
            if i not in found
        ]

        raise RuntimeError(
            f"No se encontraron los 48 packs.\n"
            f"Faltantes: {missing}"
        )

    for pack in packs:

        count = len(pack["cards"])

        print(
            f"Pack {pack['id']:02d}: "
            f"{count:3d} cartas - "
            f"{pack['name']}"
        )

    empty = [
        p for p in packs
        if p["id"] != 16
        and p["id"] != 48
        and len(p["cards"]) == 0
    ]

    if empty:
        names = ", ".join(
            f"{p['id']}: {p['name']}"
            for p in empty
        )

        raise RuntimeError(
            "Se encontraron packs sin cartas:\n" + names
        )


def main():

    print("=" * 60)
    print("TAG FORCE 2 CARD DATABASE BUILDER")
    print("=" * 60)

    print()
    print(f"Leyendo: {FAQ_FILE}")

    packs = parse()

    print(f"Datos extraídos: {len(packs)} packs")

    # Pack 48.
    for pack in packs:

        if pack["id"] == 48:

            pack["cards"] = build_checkered_flag(packs)
            pack["generated_from_packs"] = "1-47"

    # Preserve existing image/Yugipedia information.
    merge_metadata(packs)

    validate(packs)

    output = {
        "source": (
            "Local copy of GameFAQs Booster Pack FAQ 50402"
        ),
        "source_url": (
            "https://gamefaqs.gamespot.com/psp/"
            "939233-yu-gi-oh-gx-tag-force-2/faqs/50402"
        ),
        "generated_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "packs": packs,
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("=" * 60)
    print("OK")
    print("=" * 60)
    print()
    print(f"Generado:")
    print(OUT)
    print()
    print("No se utilizó conexión a GameFAQs.")


if __name__ == "__main__":
    main()