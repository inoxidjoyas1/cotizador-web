"""Regenera data/snapshot.json con precios y catalogo frescos.

SE CORRE EN TU PC DE LA OFICINA (la que alcanza Aspel SAE), NO en la nube.
Lee el Excel de cajas y los precios lista 5 desde SAE, reusando el proyecto
'simulador-cajas-3d'. Despues haz:  git add, git commit, git push  y la app
en la nube se reactualiza sola en ~1 minuto.

Uso:
    python refrescar_precios.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SIM = AQUI.parent / "simulador-cajas-3d"     # proyecto hermano con la logica + .env

if not SIM.exists():
    sys.exit(f"No encuentro el proyecto simulador en: {SIM}\n"
             "Ajusta la variable SIM en este script.")

sys.path.insert(0, str(SIM))
from src import catalog, db_sae   # noqa: E402


def main() -> None:
    boxes = catalog.load_boxes()
    prods = catalog.load_products()

    claves = [p.clave for p in prods]
    sae_prices, sae_ok = {}, False
    try:
        if db_sae.is_configured():
            sae_prices = db_sae.get_prices(claves)
            sae_ok = True
            print(f"SAE OK — {len(sae_prices)} precios leidos (lista {db_sae.LISTA_PRECIO}).")
        else:
            print("SAE no configurado (.env). Uso el precio de la columna del Excel.")
    except Exception as e:  # noqa: BLE001
        print(f"SAE no disponible ({str(e)[:80]}). Uso el precio del Excel.")

    def precio(p):
        return sae_prices.get(p.clave, p.precio)

    box_rows = []
    for b in boxes:
        il, iw, ih = b.inner
        box_rows.append(dict(nombre=b.name, ext_l=b.ext_l, ext_w=b.ext_w, ext_h=b.ext_h,
                             int_l=il, int_w=iw, int_h=ih, vol_int=round(il * iw * ih, 1),
                             menor_lado=round(min(il, iw, ih), 2), extra_kg=b.extra_weight))

    prod_rows = []
    for p in prods:
        vol = round(p.largo * p.ancho * p.alto, 3) if p.has_dims else None
        prod_rows.append(dict(clave=p.clave, articulo=p.articulo, l=p.largo, a=p.ancho,
                              h=p.alto, vol=vol, peso=p.peso, precio=precio(p),
                              tiene_medidas=p.has_dims, source=p.source))

    out = dict(sae_ok=sae_ok,
               generado=dt.datetime.now().isoformat(timespec="seconds"),
               n_boxes=len(box_rows), n_prod=len(prod_rows),
               n_con=sum(1 for r in prod_rows if r["tiene_medidas"]),
               boxes=box_rows, products=prod_rows)

    destino = AQUI / "data" / "snapshot.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nSnapshot actualizado: {destino}")
    print(f"  {out['n_prod']} productos ({out['n_con']} con medida), "
          f"{out['n_boxes']} cajas.")
    print("\nAhora sube los cambios para que la app en la nube se actualice:")
    print("  git add data/snapshot.json")
    print('  git commit -m "Actualiza precios"')
    print("  git push")


if __name__ == "__main__":
    main()
