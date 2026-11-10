"""
Busca zonas de un DEM (.tif) donde, dentro de un radio de RADIO_M metros,
exista una diferencia de elevación (desnivel) >= UMBRAL_DESNIVEL metros.
Agrupa los píxeles contiguos que cumplen la condición en "zonas" y para cada
una imprime UN punto representativo (el de mayor desnivel local) en
coordenadas decimales (lat/lon, WGS84), junto con el desnivel máximo hallado.

Requisitos:
    pip install rasterio numpy scipy --break-system-packages

Uso:
    python laderas_radio.py entrada.tif
"""

import sys
import numpy as np
import rasterio
from rasterio.transform import xy
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform as warp_transform
from scipy.ndimage import maximum_filter, minimum_filter, label, find_objects

# ----------------------- PARÁMETROS -----------------------
RADIO_M = 100.0             # radio de búsqueda en metros
UMBRAL_DESNIVEL = 800.0     # desnivel mínimo en metros
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


def disco_binario(radio_px_x, radio_px_y):
    """Genera una máscara elíptica/circular (en píxeles) equivalente al radio en metros."""
    y, x = np.ogrid[-radio_px_y:radio_px_y + 1, -radio_px_x:radio_px_x + 1]
    mascara = (x / radio_px_x) ** 2 + (y / radio_px_y) ** 2 <= 1
    return mascara


def procesar(ruta_tif):
    with rasterio.open(ruta_tif) as src:
        dem, transform, crs = reproyectar_a_metrico(src)
        nodata = src.nodata

    if nodata is not None:
        dem = np.where(dem == nodata, np.nan, dem)

    pixel_size_x = transform.a
    pixel_size_y = -transform.e

    print(f"Tamaño de píxel: {pixel_size_x:.2f} x {pixel_size_y:.2f} m")
    print(f"CRS de trabajo (métrico): {crs}")

    radio_px_x = max(1, int(round(RADIO_M / pixel_size_x)))
    radio_px_y = max(1, int(round(RADIO_M / pixel_size_y)))
    footprint = disco_binario(radio_px_x, radio_px_y)

    # NaN-safe para los filtros de máximo/mínimo
    dem_para_max = np.where(np.isnan(dem), -np.inf, dem)
    dem_para_min = np.where(np.isnan(dem), np.inf, dem)

    max_local = maximum_filter(dem_para_max, footprint=footprint, mode="nearest")
    min_local = minimum_filter(dem_para_min, footprint=footprint, mode="nearest")

    desnivel_local = max_local - min_local
    desnivel_local = np.where(np.isnan(dem), np.nan, desnivel_local)

    mascara_cumple = desnivel_local >= UMBRAL_DESNIVEL

    # ----- Agrupar píxeles contiguos que cumplen la condición en zonas -----
    estructura = np.ones((3, 3))  # conectividad 8
    etiquetas, n_zonas = label(mascara_cumple, structure=estructura)
    print(f"\nZonas detectadas con desnivel >= {UMBRAL_DESNIVEL} m en radio de {RADIO_M} m: {n_zonas}\n")

    slices = find_objects(etiquetas)

    # Coordenadas de todos los puntos representativos, para convertir en batch
    puntos_px = []  # (fila, col, desnivel)

    for i, sl in enumerate(slices, start=1):
        if sl is None:
            continue
        region_local = etiquetas[sl] == i
        desnivel_region = np.where(region_local, desnivel_local[sl], -np.inf)

        # Punto representativo = el de mayor desnivel local dentro de la zona
        idx_local = np.unravel_index(np.argmax(desnivel_region), desnivel_region.shape)
        fila = sl[0].start + idx_local[0]
        col = sl[1].start + idx_local[1]
        desnivel_max = float(desnivel_local[fila, col])

        puntos_px.append((fila, col, desnivel_max))

    if not puntos_px:
        print("No se encontraron zonas que cumplan la condición.")
        return []

    # Convertir todas las coordenadas de píxel -> CRS métrico -> lat/lon (WGS84)
    xs_m, ys_m = [], []
    for fila, col, _ in puntos_px:
        x_m, y_m = xy(transform, fila, col)
        xs_m.append(x_m)
        ys_m.append(y_m)

    lons, lats = warp_transform(crs, "EPSG:4326", xs_m, ys_m)

    resultados = []
    for (fila, col, desnivel_max), lon, lat in zip(puntos_px, lons, lats):
        resultados.append({"lon": lon, "lat": lat, "desnivel_max_m": desnivel_max})
        print(f"coor:{lat:.6f}, {lon:.6f}  ->  desnivel máximo en el radio: {desnivel_max:.1f} m")

    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python laderas_radio.py entrada.tif")
        sys.exit(1)

    procesar(sys.argv[1])