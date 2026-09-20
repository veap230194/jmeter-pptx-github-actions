# JMeter Performance Report

Proyecto para ejecutar una prueba JMeter desde GitHub Actions y completar automáticamente una plantilla PowerPoint con los resultados.

## Flujo

1. GitHub Actions descarga e instala JMeter 5.6.3.
2. Ejecuta `jmeter/performance-test.jmx` en modo no gráfico.
3. Guarda los resultados en `output/results.jtl`.
4. Calcula horarios, transacciones, TPS y tiempos de respuesta.
5. Genera una gráfica de usuarios activos y TPS.
6. Completa `template/Ejemplo.pptx`.
7. Publica el PPTX y los resultados como artifact durante 30 días.

El workflow no escribe en el repositorio, no crea commits y no abre pull requests.

## Configuración requerida

En GitHub, ingresar a **Settings > Secrets and variables > Actions > New repository secret** y crear:

```text
RAPIDAPI_KEY
```

La clave no debe escribirse en el JMX ni en el workflow. El plan usa:

```text
${__P(RAPIDAPI_KEY,)}
```

## Ejecución en GitHub

1. Abrir la pestaña **Actions**.
2. Elegir **JMeter performance test and PPTX report**.
3. Seleccionar **Run workflow**.
4. Ingresar usuarios, ramp-up, duración, iteraciones y usuario objetivo.
   Para programar el inicio, completar opcionalmente `scheduled_start` con el formato
   `AAAA-MM-DD HH:MM` en horario `America/Lima`. La hora puede estar hasta 4 horas en el futuro.
5. Descargar `performance-report-<número>` desde la sección **Artifacts** de la ejecución.

El artifact contiene el reporte PowerPoint, JTL, métricas JSON, gráfica y dashboard HTML de JMeter.

## Corte automático por falta de respuestas exitosas

JMeter detiene la prueba si transcurren 180 segundos sin ninguna respuesta exitosa. El contador
comienza al arrancar la prueba y se reinicia cada vez que llega una respuesta correcta. Cuando se
activa el corte, se genera `output/fail-fast.txt`, se publican los resultados parciales y GitHub
Actions marca la ejecución en rojo.

## Cálculos

- **Hora de inicio:** menor `timeStamp` del JTL.
- **Hora de finalización:** mayor `timeStamp + elapsed`.
- **Transacciones:** número de muestras del JTL.
- **TPS promedio:** transacciones totales / duración efectiva.
- **TPS máximo:** mayor cantidad de muestras iniciadas dentro de un segundo.
- **Usuarios activos:** mayor `allThreads` o `grpThreads` informado en cada segundo.
- **Exitosas/fallidas:** valor de la columna `success`.

Los horarios se muestran en `America/Lima`.

## Prueba local usando el JTL incluido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/analyze_jmeter.py \
  --jtl tests/results.jtl \
  --metrics output/metrics.json \
  --chart output/load-chart.png

python scripts/generate_report.py \
  --template template/Ejemplo.pptx \
  --metrics output/metrics.json \
  --chart output/load-chart.png \
  --output output/Reporte_Performance_demo.pptx

python scripts/validate_report.py output/Reporte_Performance_demo.pptx
```

En PowerShell, activar el entorno con `.venv\\Scripts\\Activate.ps1` y escribir cada comando en una sola línea o usar el acento grave para continuarlo.

## Adaptación a otra API

El JMX incluido conserva el endpoint de ejemplo recibido. Para usar una API interna se deben parametrizar el host, ruta, cabeceras y credenciales correspondientes. Los secretos deben permanecer en GitHub Secrets.
