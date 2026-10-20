#!/usr/bin/env python3
# Descarga las imágenes de los packs de Link Evolution desde Yugipedia.
# Requisitos: py -m pip install requests beautifulsoup4

import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

SHOP_URL = "https://yugipedia.com/wiki/Yu-Gi-Oh!_Legacy_of_the_Duelist:_Link_Evolution/Card_Shop"
OUTPUT_DIR = Path("images") / "packs-link-evolution"
DELAY_SECONDS = 0.7

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}


def clean_filename(name: str) -> str:
    """Convierte el texto del enlace en un nombre de archivo seguro."""
    name = unquote(name).strip()
    name = re.sub(r'[<>:"/\\\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or "pack_sin_nombre"


def page_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def find_pack_links(soup: BeautifulSoup):
    """Busca los enlaces de packs en la sección 'List' de la tabla de contenidos."""
    links = []
    seen = set()

    # Localiza el encabezado List (puede ser un h2/h3/h4 según la página).
    list_heading = None
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if heading.get_text(" ", strip=True).casefold() == "list":
            list_heading = heading
            break

    if list_heading:
        # Recorre el contenido después del encabezado hasta el próximo encabezado
        # del mismo nivel o superior.
        level = int(list_heading.name[1])
        for node in list_heading.find_all_next():
            if re.fullmatch(r"h[1-6]", node.name or "") and int(node.name[1]) <= level:
                break
            if node.name != "a" or not node.get("href"):
                continue
            label = node.get_text(" ", strip=True)
            href = urljoin(SHOP_URL, node["href"])
            if not label or "/wiki/" not in href:
                continue
            if "redlink=1" in href or ":" in label:
                continue
            if href.rstrip("/") == SHOP_URL.rstrip("/"):
                continue
            key = href.split("#", 1)[0]
            if key not in seen and "(Link_Evolution)" in key:
                seen.add(key)
                links.append((label, key))
        if links:
            return links

    # Alternativa si Yugipedia cambia la estructura del encabezado:
    # toma enlaces con patrón de página de pack de Link Evolution.
    for a in soup.select("a[href]"):
        label = a.get_text(" ", strip=True)
        href = urljoin(SHOP_URL, a["href"])
        if label and "(Link_Evolution)" in href and "/wiki/" in href:
            key = href.split("#", 1)[0]
            if key not in seen:
                seen.add(key)
                links.append((label, key))
    return links


def image_from_pack_page(soup: BeautifulSoup, page_url: str):
    """Encuentra la imagen de pack de la ficha, normalmente en el infobox a la derecha."""
    # Preferir imágenes que enlacen a un archivo PNG/JPG/SVG y estén dentro del infobox.
    containers = soup.select(".portable-infobox, .infobox, table.infobox")
    candidates = []
    for container in containers:
        for img in container.select("img[src], img[data-src]"):
            src = img.get("src") or img.get("data-src")
            if src:
                candidates.append((src, img.get("alt", "")))

    # Si no se encontró infobox, revisar todas las imágenes de la página.
    if not candidates:
        for img in soup.select("img[src], img[data-src]"):
            src = img.get("src") or img.get("data-src")
            if src:
                candidates.append((src, img.get("alt", "")))

    def score(item):
        src, alt = item
        text = (src + " " + alt).casefold()
        points = 0
        if "pack" in text:
            points += 5
        if "le.png" in text or "-le." in text:
            points += 4
        if "yugipedia" in src.casefold() or "ms." in src.casefold():
            points += 1
        if any(x in text for x in ("logo", "icon", "wiki.png", "commons-logo")):
            points -= 10
        return points

    candidates.sort(key=score, reverse=True)
    for src, alt in candidates:
        if any(x in (src + " " + alt).casefold() for x in ("logo", "commons-logo")):
            continue
        if src.startswith("//"):
            return "https:" + src
        return urljoin(page_url, src)
    return None


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"Consultando la lista de packs:\n{SHOP_URL}\n")
    try:
        shop_soup = page_soup(session, SHOP_URL)
    except requests.RequestException as exc:
        print(f"ERROR al abrir la página principal: {exc}")
        sys.exit(1)

    packs = find_pack_links(shop_soup)
    if not packs:
        print("No encontré enlaces de packs bajo 'List'. "
              "Puede haber cambiado el HTML de Yugipedia.")
        sys.exit(2)

    print(f"Encontré {len(packs)} enlaces. Carpeta destino: {OUTPUT_DIR.resolve()}\n")
    ok = 0
    failed = []

    for index, (pack_name, pack_url) in enumerate(packs, start=1):
        # El nombre final deriva del texto visible del hyperlink, sin renombrado manual.
        filename = clean_filename(pack_name)
        print(f"[{index}/{len(packs)}] {pack_name}")

        try:
            pack_soup = page_soup(session, pack_url)
            image_url = image_from_pack_page(pack_soup, pack_url)
            if not image_url:
                raise RuntimeError("No se encontró una imagen en la ficha del pack")

            response = session.get(image_url, timeout=30)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            suffix = Path(image_url.split("?", 1)[0]).suffix.lower()
            if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
                suffix = ".png" if "png" in content_type else ".jpg" if "jpeg" in content_type else ".png"

            destination = OUTPUT_DIR / f"{filename}{suffix}"
            destination.write_bytes(response.content)
            print(f"    OK -> {destination.name} ({len(response.content):,} bytes)")
            ok += 1
        except (requests.RequestException, RuntimeError, OSError) as exc:
            print(f"    ERROR: {exc}")
            failed.append((pack_name, pack_url, str(exc)))

        time.sleep(DELAY_SECONDS)

    print(f"\nTerminado: {ok}/{len(packs)} imágenes descargadas.")
    if failed:
        report = OUTPUT_DIR / "descargas_fallidas.txt"
        report.write_text(
            "Packs que no se pudieron descargar:\n\n" +
            "\n".join(f"{name}\n{url}\nError: {error}\n" for name, url, error in failed),
            encoding="utf-8"
        )
        print(f"Fallaron {len(failed)}. Dejé el detalle en: {report}")
    print(f"Carpeta final: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
