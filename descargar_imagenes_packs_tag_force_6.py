
from pathlib import Path
from urllib.parse import urljoin, unquote
import csv
import re
import time

import requests
from bs4 import BeautifulSoup


# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------

URL_GALERIA = (
    "https://yugipedia.com/wiki/"
    "Yu-Gi-Oh!_5D%27s_Tag_Force_6_Booster_Pack_gallery"
)

DESTINO = Path(
    r"J:\Users\marco\OneDrive\Documents\GitHub"
    r"\Nehalem95.github.io\images\packs-tag-force-6"
)

CSV_SALIDA = DESTINO / "packs_tag_force_6.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    )
}

ESPERA_ENTRE_DESCARGAS = 0.3
TIMEOUT = 30


# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------

def obtener_url_imagen(img, pagina_url):
    """Obtiene la URL de la imagen, intentando recuperar el original."""

    candidatos = [
        img.get("data-src"),
        img.get("data-original"),
        img.get("src"),
    ]

    # Algunas páginas guardan la URL en srcset.
    for atributo in ("data-srcset", "srcset"):
        srcset = img.get(atributo)
        if srcset:
            primera_opcion = srcset.split(",")[0].strip().split()[0]
            candidatos.insert(0, primera_opcion)

    url = next(
        (
            urljoin(pagina_url, valor.strip())
            for valor in candidatos
            if valor and valor.strip()
            and not valor.startswith("data:")
        ),
        None,
    )

    if not url:
        return None

    # Convierte las miniaturas de MediaWiki a la URL del original.
    # Ejemplo:
    # /images/thumb/a/ab/Carta.jpg/200px-Carta.jpg
    # -> /images/a/ab/Carta.jpg
    url = re.sub(
        r"/thumb/(.+)/[^/]+/\d+px-[^/]+$",
        r"/\1",
        url,
    )

    return url


def nombre_desde_alt(img, numero):
    """Usa el texto alternativo como nombre orientativo del sobre."""

    nombre = (
        img.get("alt")
        or img.get("title")
        or f"Sobre {numero}"
    )

    nombre = re.sub(r"\s+", " ", nombre).strip()
    return nombre or f"Sobre {numero}"


def extension_desde_respuesta(respuesta, url):
    """Determina la extensión usando el tipo de contenido."""

    tipo = respuesta.headers.get("Content-Type", "").lower()

    if "image/jpeg" in tipo or "image/jpg" in tipo:
        return ".jpg"
    if "image/png" in tipo:
        return ".png"
    if "image/webp" in tipo:
        return ".webp"
    if "image/gif" in tipo:
        return ".gif"

    ruta = unquote(url.split("?")[0]).lower()
    coincidencia = re.search(r"\.(jpe?g|png|webp|gif)$", ruta)

    if coincidencia:
        extension = coincidencia.group(1)
        return ".jpg" if extension in ("jpg", "jpeg") else "." + extension

    return ".jpg"


def encontrar_imagenes(soup):
    """Extrae las imágenes de las galerías, conservando su orden."""

    contenido = soup.select_one("#mw-content-text") or soup
    imagenes = []

    # Prioriza contenedores típicos de galerías de MediaWiki.
    selectores = [
        ".mw-gallery",
        ".gallery",
        "ul.gallery",
        ".gallerybox",
        ".gallery-item",
        ".wikia-gallery",
    ]

    contenedores = []
    for selector in selectores:
        contenedores.extend(contenido.select(selector))

    # Elimina contenedores repetidos y anidados para evitar duplicados.
    if contenedores:
        ids_vistos = set()
        contenedores_unicos = []

        for contenedor in contenedores:
            identificador = id(contenedor)
            if identificador not in ids_vistos:
                ids_vistos.add(identificador)
                contenedores_unicos.append(contenedor)

        for contenedor in contenedores_unicos:
            imagenes.extend(contenedor.select("img"))
    else:
        # Alternativa si la página no usa los contenedores habituales.
        imagenes = contenido.select("figure img, table img")

    resultado = []
    urls_vistas = set()

    for img in imagenes:
        url = obtener_url_imagen(img, URL_GALERIA)

        if not url:
            continue

        url_limpia = url.split("?")[0].lower()

        if not re.search(r"\.(jpe?g|png|webp|gif)$", url_limpia):
            continue

        # Excluye iconos pequeños conocidos por su nombre.
        if any(
            palabra in url_limpia
            for palabra in (
                "edit-icon",
                "commons-logo",
                "poweredby",
                "wikimedia-button",
            )
        ):
            continue

        if url in urls_vistas:
            continue

        urls_vistas.add(url)
        resultado.append({
            "nombre": nombre_desde_alt(img, len(resultado) + 1),
            "url": url,
        })

    return resultado


# --------------------------------------------------
# DESCARGA
# --------------------------------------------------

def main():
    DESTINO.mkdir(parents=True, exist_ok=True)

    sesion = requests.Session()
    sesion.headers.update(HEADERS)

    print("Consultando la galería de Yugipedia...")
    print(URL_GALERIA)

    try:
        respuesta = sesion.get(URL_GALERIA, timeout=TIMEOUT)
        respuesta.raise_for_status()
    except requests.RequestException as error:
        print(f"\nERROR al consultar Yugipedia: {error}")
        return

    soup = BeautifulSoup(respuesta.text, "html.parser")
    imagenes = encontrar_imagenes(soup)

    if not imagenes:
        print(
            "\nNo se encontraron imágenes en los contenedores "
            "esperados de la galería."
        )
        print(
            "Es posible que Yugipedia haya cambiado su estructura "
            "o que la página bloquee la consulta."
        )
        print("No se descargó ningún archivo.")
        return

    print(f"\nImágenes encontradas: {len(imagenes)}")
    print(f"Destino: {DESTINO}\n")

    filas_csv = []
    exitosas = 0
    fallidas = 0

    total = len(imagenes)
    ancho = max(2, len(str(total)))

    for indice, imagen in enumerate(imagenes, start=1):
        numero = str(indice).zfill(ancho)
        nombre = imagen["nombre"]
        url = imagen["url"]

        try:
            descarga = sesion.get(url, timeout=TIMEOUT)
            descarga.raise_for_status()

            tipo = descarga.headers.get("Content-Type", "").lower()

            if not tipo.startswith("image/"):
                raise ValueError(
                    f"El servidor no devolvió una imagen ({tipo or 'tipo desconocido'})"
                )

            extension = extension_desde_respuesta(descarga, url)
            archivo = DESTINO / f"{numero}{extension}"
            archivo.write_bytes(descarga.content)

            exitosas += 1
            estado = "OK"
            bytes_guardados = len(descarga.content)

            print(
                f"[{indice}/{total}] OK  {archivo.name}"
                f" — {nombre}"
            )

        except (requests.RequestException, OSError, ValueError) as error:
            fallidas += 1
            estado = f"ERROR: {error}"
            bytes_guardados = 0
            archivo = None

            print(
                f"[{indice}/{total}] ERROR — {nombre}: {error}"
            )

        filas_csv.append({
            "numero": indice,
            "nombre": nombre,
            "archivo": archivo.name if archivo else "",
            "url": url,
            "estado": estado,
            "bytes": bytes_guardados,
        })

        time.sleep(ESPERA_ENTRE_DESCARGAS)

    # Registro de resultados, incluso si algunas descargas fallaron.
    with CSV_SALIDA.open("w", newline="", encoding="utf-8-sig") as f:
        campos = [
            "numero",
            "nombre",
            "archivo",
            "url",
            "estado",
            "bytes",
        ]
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas_csv)

    print("\n" + "=" * 50)
    print("DESCARGA FINALIZADA")
    print(f"Encontradas: {total}")
    print(f"Descargadas: {exitosas}")
    print(f"Fallidas: {fallidas}")
    print(f"Registro CSV: {CSV_SALIDA}")
    print(f"Carpeta de imágenes: {DESTINO}")
    print("=" * 50)


if __name__ == "__main__":
    main()
