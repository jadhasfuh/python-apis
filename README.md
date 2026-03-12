# Servicios Python - Migración a EasyPanel

## Resumen
Son 2 servicios Python que se necesitan levantar en la misma VPS donde está n8n.
Como estarán en la misma red Docker de EasyPanel, **NO necesitan puerto público expuesto**, solo acceso interno desde n8n.

---

## 1. pdf-extractor-api (Puerto 5050)

**Qué hace:** Extrae campos de formularios PDF y detecta páginas de facturas en PDFs multi-hoja.

**Endpoints:**
- `POST /extract` — Extrae campos de un PDF
- `POST /pdf/find-invoice-page` — Detecta páginas de factura
- `GET /health` — Health check

**Cómo levantar en EasyPanel:**

Opción A — Crear como App Docker:
1. Crear nuevo servicio en EasyPanel
2. Subir los 3 archivos: `Dockerfile`, `requirements.txt`, `extractor_api.py`
3. Build desde Dockerfile
4. Puerto interno: `5050`
5. **No exponer al público**

Opción B — Desde línea de comandos (si hay SSH):
```bash
cd pdf-extractor-api
docker build -t pdf-extractor-api .
docker run -d --name pdf-extractor-api --network easypanel -p 5050:5050 --restart always pdf-extractor-api
```

**Hostname interno para n8n:** `pdf-extractor-api:5050` (ajustar según nombre del servicio en EasyPanel)

---

## 2. sf-upload-proxy (Puerto 5051)

**Qué hace:** Recibe archivos y los sube a Salesforce (ContentVersion + ContentDocumentLink).

**Endpoints:**
- `POST /upload-to-salesforce` — Sube archivo a Salesforce
- `GET /health` — Health check

**Cómo levantar en EasyPanel:**

Opción A — Crear como App Docker:
1. Crear nuevo servicio en EasyPanel
2. Subir los 3 archivos: `Dockerfile`, `requirements.txt`, `sf_upload_proxy.py`
3. Build desde Dockerfile
4. Puerto interno: `5051`
5. **No exponer al público**

Opción B — Desde línea de comandos (si hay SSH):
```bash
cd sf-upload-proxy
docker build -t sf-upload-proxy .
docker run -d --name sf-upload-proxy --network easypanel -p 5051:5051 --restart always sf-upload-proxy
```

**Hostname interno para n8n:** `sf-upload-proxy:5051` (ajustar según nombre del servicio en EasyPanel)

---

## Verificación

Una vez levantados, desde n8n o desde dentro de la VPS:

```bash
# PDF Extractor
curl http://pdf-extractor-api:5050/health

# SF Upload Proxy
curl http://sf-upload-proxy:5051/health
```

Ambos deben responder `{"status": "healthy"}`.

---

## Actualización en n8n

Una vez funcionando, cambiar en los workflows:

| Antes | Después |
|-------|---------|
| `http://157.173.199.130:5050/extract` | `http://pdf-extractor-api:5050/extract` |
| `http://157.173.199.130:5050/pdf/find-invoice-page` | `http://pdf-extractor-api:5050/pdf/find-invoice-page` |
| `http://157.173.199.130:5051/upload-to-salesforce` | `http://sf-upload-proxy:5051/upload-to-salesforce` |

> **Nota:** Los hostnames internos dependen de cómo se nombren los servicios en EasyPanel. Ajustar según corresponda.
