"""Logica pura del cotizador web (sin UI, sin base de datos).

Reconoce un pedido pegado como texto libre, lo cotiza (precio snapshot) y
recomienda la caja mas chica donde cabe (aproximado volumetrico, sin 3D).

Los datos vienen de data/snapshot.json (foto del catalogo tomada de Aspel SAE).
Portado del proyecto simulador-cajas-3d (order_parser + quote) + heuristica de
caja validada.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

DATA = Path(__file__).resolve().parent / "data" / "snapshot.json"

# Umbral de confianza para aceptar un emparejamiento difuso (0..100).
MATCH_THRESHOLD = 72

_STOPWORDS = {"de", "la", "el", "un", "una", "con", "para", "y", "por", "pieza",
              "piezas", "pza", "pzas", "pzs", "pz", "unidad", "unidades", "ud", "uds"}


# --------------------------------------------------------------------- datos
@dataclass
class Catalogo:
    products: list[dict]
    boxes: list[dict]              # ordenadas por volumen interior ascendente
    generado: str
    sae_ok: bool
    by_clave: dict = field(default_factory=dict)
    choices: dict = field(default_factory=dict)
    prod_by_clave: dict = field(default_factory=dict)


def cargar(path: Path | None = None) -> Catalogo:
    d = json.loads(Path(path or DATA).read_text(encoding="utf-8"))
    prods = d["products"]
    boxes = sorted(d["boxes"], key=lambda b: b["vol_int"])
    cat = Catalogo(products=prods, boxes=boxes,
                   generado=d.get("generado", ""), sae_ok=d.get("sae_ok", False))
    cat.by_clave = {p["clave"].upper(): p for p in prods}
    cat.choices = {p["clave"]: _norm(f"{p['clave']} {p['articulo']}") for p in prods}
    cat.prod_by_clave = {p["clave"]: p for p in prods}
    return cat


# ------------------------------------------------------------------ utiles
def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _strip_bullets(line: str) -> str:
    line = re.sub(r"^\s*[-*•·>]+\s*", "", line)
    line = re.sub(r"^\s*\d+\s*[\).]\s+", "", line)
    return line.strip()


def _extract_qty(text: str) -> tuple[int, str]:
    """Extrae la cantidad. Reconoce '2 PA01', '2x PA01', 'PA01 x2', '3 pzas'."""
    m = re.match(r"^\s*(\d+)\s*[xX]?\s+(.+)$", text)
    if m:
        return max(int(m.group(1)), 1), m.group(2).strip()
    m = re.search(r"(?:^|\s)[xX*]\s*(\d+)\b", text)
    if m:
        qty = int(m.group(1))
        text = (text[:m.start()] + text[m.end():]).strip()
        return max(qty, 1), text
    m = re.search(r"\b(\d+)\s*(?:pz|pzs|pzas|piezas|pieza|unidades|uds?)\b", text, re.I)
    if m:
        qty = int(m.group(1))
        text = (text[:m.start()] + text[m.end():]).strip()
        return max(qty, 1), text
    return 1, text.strip()


def _clean_article_text(text: str) -> str:
    text = re.sub(r"[xX]\s*\d+", " ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    tokens = [t for t in _norm(text).split() if t not in _STOPWORDS]
    return " ".join(tokens).strip()


def _match_article(text: str, cat: Catalogo) -> tuple[Optional[dict], float]:
    # 1) clave exacta en algun token
    for tok in re.findall(r"[A-Za-z]{1,4}\d{1,3}", text):
        if tok.upper() in cat.by_clave:
            return cat.by_clave[tok.upper()], 100.0
    query = _clean_article_text(text)
    if not query:
        return None, 0.0
    # 2) difuso contra "clave descripcion"
    best = process.extractOne(query, cat.choices, scorer=fuzz.token_set_ratio)
    if best is None:
        return None, 0.0
    _s, score, clave = best
    return cat.prod_by_clave[clave], float(score)


# ------------------------------------------------------------- reconocimiento
@dataclass
class Linea:
    raw: str
    qty: int
    clave: Optional[str]
    articulo: Optional[str]
    precio: Optional[float]
    importe: float
    score: float
    matched: bool
    tiene_medidas: bool


def parse_pedido(texto: str, cat: Catalogo) -> list[Linea]:
    lineas: list[Linea] = []
    for raw in texto.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        body = _strip_bullets(raw)
        if not body:
            continue
        qty, rest = _extract_qty(body)
        prod, score = _match_article(rest, cat)
        if prod and score >= MATCH_THRESHOLD:
            precio = prod.get("precio")
            importe = round((precio or 0.0) * qty, 2)
            lineas.append(Linea(raw, qty, prod["clave"], prod["articulo"],
                                precio, importe, round(score, 1), True,
                                bool(prod.get("tiene_medidas"))))
        else:
            if _clean_article_text(rest):
                lineas.append(Linea(raw, qty, None, None, None, 0.0,
                                    round(score, 1), False, False))
    return lineas


# ------------------------------------------------------------------ cotizacion
@dataclass
class Resumen:
    total_piezas: int
    total_articulos: int
    total_importe: float
    volumen_total: float
    caja: str
    alternativa: str
    ocupacion: Optional[float]
    avisos: list[str]


def _pieza_cabe(p: dict, c: dict) -> bool:
    pd = sorted([p["l"], p["a"], p["h"]], reverse=True)
    bd = sorted([c["int_l"], c["int_w"], c["int_h"]], reverse=True)
    return all(pd[i] <= bd[i] + 1e-3 for i in range(3))


def recomendar_caja(order: list[tuple[dict, int]], cat: Catalogo,
                    factor: float) -> tuple[str, str, Optional[float], list[str]]:
    """Devuelve (caja, alternativa, ocupacion, avisos)."""
    dim = [(p, q) for p, q in order if p.get("tiene_medidas")]
    if not dim:
        return "(sin articulos con medida)", "", None, []
    tot_vol = sum(p["vol"] * q for p, q in dim)
    avisos: list[str] = []

    for i, c in enumerate(cat.boxes):
        if all(_pieza_cabe(p, c) for p, _ in dim) and tot_vol <= c["vol_int"] * factor:
            alterna = ""
            for c2 in cat.boxes[i + 1:]:
                if all(_pieza_cabe(p, c2) for p, _ in dim):
                    alterna = f"{c2['nombre']} (con holgura)"
                    break
            return c["nombre"], alterna, tot_vol / c["vol_int"], avisos

    # ninguna caja sola alcanza
    cabe = [c for c in cat.boxes if all(_pieza_cabe(p, c) for p, _ in dim)]
    if not cabe:
        avisos.append("Hay una pieza que no cabe ni en la caja mas grande; empaque especial.")
        return "NINGUNA caja estandar", "", None, avisos
    big = cabe[-1]
    import math
    n = max(2, math.ceil(tot_vol / (big["vol_int"] * factor)))
    avisos.append(f"El pedido no cabe en una sola caja; se estiman {n} cajas de esa medida "
                  "(o dividir el envio).")
    return f"{n} x {big['nombre']}", "", None, avisos


def cotizar(texto: str, cat: Catalogo, factor: float = 0.70):
    """Punto de entrada: devuelve (lineas, resumen)."""
    lineas = parse_pedido(texto, cat)

    # acumular por clave para el calculo de caja
    acc: dict[str, int] = {}
    for ln in lineas:
        if ln.matched and ln.clave:
            acc[ln.clave] = acc.get(ln.clave, 0) + ln.qty
    order = [(cat.prod_by_clave[c], n) for c, n in acc.items() if c in cat.prod_by_clave]

    caja, alterna, ocup, avisos = recomendar_caja(order, cat, factor)

    total_piezas = sum(ln.qty for ln in lineas if ln.matched)
    total_art = len(acc)
    total_importe = round(sum(ln.importe for ln in lineas if ln.matched), 2)
    vol_total = round(sum(cat.prod_by_clave[c]["vol"] * n
                          for c, n in acc.items()
                          if cat.prod_by_clave.get(c, {}).get("tiene_medidas")), 1)

    sin_medida = sum(1 for ln in lineas if ln.matched and not ln.tiene_medidas)
    sin_precio = sum(1 for ln in lineas if ln.matched and ln.precio is None)
    no_recon = sum(1 for ln in lineas if not ln.matched)
    if sin_medida:
        avisos.insert(0, f"{sin_medida} articulo(s) SIN MEDIDA: se cotizan pero NO cuentan para la caja.")
    if sin_precio:
        avisos.append(f"{sin_precio} articulo(s) sin precio en el snapshot.")
    if no_recon:
        avisos.append(f"{no_recon} renglon(es) NO reconocidos: corrige el texto o usa la clave.")

    resumen = Resumen(total_piezas, total_art, total_importe, vol_total,
                      caja, alterna, ocup, avisos)
    return lineas, resumen
