"""
A partir de un DEM (.tif), grafica el mapa topográfico (curvas de nivel +
sombreado de relieve) en un radio de RADIO_GRAFICO_M metros alrededor de
una coordenada (lat, lon en decimal, WGS84) ingresada por el usuario.

Requisitos:
    pip install rasterio numpy matplotlib --break-system-packages

Uso:
    python mapa_topografico.py entrada.tif LAT LON
    python mapa_topografico.py entrada.tif          (te pide lat/lon por teclado)
"""


import sys
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform as warp_transform
from rasterio.windows import Window
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

# ----------------------- PARÁMETROS -----------------------
RADIO_GRAFICO_M = 5000.0     # radio del área a graficar, en metros
N_CURVAS_NIVEL = 25          # cantidad aproximada de curvas de nivel
# ------------------------------------------------------------


def reproyectar_a_metrico(src):
    """Si el CRS está en grados (lat/lon), reproyecta a UTM automáticamente."""
    if src.crs is None or src.crs.is_geographic:
        lon = (src.bounds.left + src.bounds.right) / 2
        lat = (src.bounds.top + src.bounds.bottom) / 2
        zona = int((lon + 180) / 6) + 1
        epsg = 32600 + zona if lat >= 0 else 32700 + zona
        dst_crs = f"EPSG:{epsg}"

        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        dem = np.empty((height, width), dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dem,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
        )
        return dem, transform, dst_crs
    else:
        dem = src.read(1).astype(np.float32)
        return dem, src.transform, src.crs


def graficar(ruta_tif, lat, lon):
    with rasterio.open(ruta_tif) as src:
        dem, transform, crs = reproyectar_a_metrico(src)
        nodata = src.nodata

    if nodata is not None:
        dem = np.where(dem == nodata, np.nan, dem)

    pixel_size_x = transform.a
    pixel_size_y = -transform.e

    # Convertir la coordenada lat/lon ingresada al CRS métrico del DEM
    x_m, y_m = warp_transform("EPSG:4326", crs, [lon], [lat])
    x_m, y_m = x_m[0], y_m[0]

    # Convertir la coordenada métrica a fila/columna de píxel
    col_c, fila_c = ~transform * (x_m, y_m)
    col_c, fila_c = int(round(col_c)), int(round(fila_c))

    radio_px_x = int(round(RADIO_GRAFICO_M / pixel_size_x))
    radio_px_y = int(round(RADIO_GRAFICO_M / pixel_size_y))

    fila_ini = max(0, fila_c - radio_px_y)
    fila_fin = min(dem.shape[0], fila_c + radio_px_y)
    col_ini = max(0, col_c - radio_px_x)
    col_fin = min(dem.shape[1], col_c + radio_px_x)

    if fila_ini >= fila_fin or col_ini >= col_fin:
        raise ValueError("La coordenada ingresada está fuera del área cubierta por el DEM.")

    recorte = dem[fila_ini:fila_fin, col_ini:col_fin]

    if np.all(np.isnan(recorte)):
        raise ValueError("El área recortada no tiene datos válidos de elevación.")

    # Extensión en metros relativos al punto central, para los ejes del gráfico
    extent = [
        (col_ini - col_c) * pixel_size_x,
        (col_fin - col_c) * pixel_size_x,
        (fila_fin - fila_c) * -pixel_size_y,
        (fila_ini - fila_c) * -pixel_size_y,
    ]

    # --- Sombreado de relieve (hillshade) ---
    ls = LightSource(azdeg=315, altdeg=45)
    rgb = ls.shade(recorte, cmap=plt.cm.terrain, vert_exag=1.5, blend_mode="soft")

    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(rgb, extent=extent, origin="upper")

    # --- Curvas de nivel ---
    niveles = np.linspace(np.nanmin(recorte), np.nanmax(recorte), N_CURVAS_NIVEL)
    cs = ax.contour(
        recorte, levels=niveles, extent=extent, origin="upper",
        colors="black", linewidths=0.4, alpha=0.6
    )
    ax.clabel(cs, inline=True, fontsize=6, fmt="%d m")

    # --- Marcar el punto ingresado (centro) ---
    ax.plot(0, 0, marker="*", color="red", markersize=16, markeredgecolor="black")
    ax.annotate(f"  ({lat:.5f}, {lon:.5f})", (0, 0), color="red", fontsize=9, weight="bold")

    # --- Barra de color de referencia con la escala de elevación real ---
    sm = plt.cm.ScalarMappable(cmap="terrain")
    sm.set_array(recorte)
    sm.set_clim(np.nanmin(recorte), np.nanmax(recorte))
    cbar = fig.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label("Elevación (m)")

    ax.set_xlabel("Distancia Este-Oeste desde el punto (m)")
    ax.set_ylabel("Distancia Norte-Sur desde el punto (m)")
    ax.set_title(f"Mapa topográfico — radio {RADIO_GRAFICO_M/1000:.0f} km alrededor de ({lat:.5f}, {lon:.5f})")
    ax.set_aspect("equal")

    plt.tight_layout()
    salida = "mapa_topografico.png"
    plt.savefig(salida, dpi=200)
    print(f"Gráfico guardado en: {salida}")
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        ruta_tif = sys.argv[1]
        lat = float(sys.argv[2])
        lon = float(sys.argv[3])
    elif len(sys.argv) == 2:
        ruta_tif = sys.argv[1]
        lat = float(input("Latitud (decimal, WGS84): "))
        lon = float(input("Longitud (decimal, WGS84): "))
    else:
        print("Uso: python mapa_topografico.py entrada.tif [LAT LON]")
        sys.exit(1)

    graficar(ruta_tif, lat, lon)