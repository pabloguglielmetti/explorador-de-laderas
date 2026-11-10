ladera.py es el código que lee el archivo .tif (modelo topográfico), donde se define el radio y umbral de desnivel que se buscan 
y te devuelve aquellas coordenadas donde, dentro del radio definido, hay mas que el umbral en desnivel. El desnivel máximo dentro del 
radio también te lo entrega junto con las coordenas. Esta herramienta esta pensada para buscar cerros bacanes y hacer una comparación 
cuantitativa de sus laderas mas escarpadas.

El código mapa.py sirve para graficar el archivo .tif al rededor de una coordenada especifica. Este se creó para verificar la validez de la 
información del archivo .tif, pues muchas veces estros traen errores.
