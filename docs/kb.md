# Docs de conocimiento — Nix Cloud (corpus sintético del Build)

## Plan y precios
Nix Cloud ofrece tres planes. **Starter** (gratis): 2 proyectos, 10k requests/mes, comunidad. **Pro** ($19/mes): proyectos ilimitados, 500k requests/mes, soporte por email en 24 h, 99.5% SLA. **Enterprise** ($499/mes): SSO/SAML, SLA 99.99%, soporte dedicado, VPC privada, export de logs a tu bucket.
Las upgrades son prorrateadas al día. Downgrade aplica al inicio del siguiente ciclo. Reembolsos: 14 días sin preguntas en el primer pago.

## Límites de la API
Rate limit por defecto: 60 requests/minuto (Pro 600). Al exceder, la API devuelve 429 con header `Retry-After`. El límite de payload es 1 MB por request. Timeouts de server-side: 30 s (streaming 120 s). Cada respuesta incluye `X-Request-Id` — pedilo al reportar problemas.

## Autenticación
La API usa API keys con prefijo `nix_live_` (producción) o `nix_test_` (sandbox). Van en header `Authorization: Bearer <key>`. Las keys se rotan desde Dashboard → Settings → API Keys; la rotación no revoca la vieja hasta 24 h después (periodo de gracia). Si una key se filtra, revocar inmediatamente desde el dashboard (revocación inmediata, sin gracia).

## Webhooks
Los webhooks entregan eventos POST con firma `X-Nix-Signature` (HMAC-SHA256 del body con tu signing secret). Responde 2xx en menos de 5 s o el delivery se reintenta con backoff exponencial: 1 m, 5 m, 30 m, 2 h, 6 h (5 intentos, luego a la cola de dead-letters visible en el dashboard). El payload incluye `event`, `created_at` y `data`. Verificá la firma antes de procesar.

## Errores comunes
`401 invalid_key`: key mal formateada o revocada. `403 org_mismatch`: la key no pertenece a la org del recurso. `409 version_conflict`: dos escrituras simultáneas sobre el mismo recurso — resolvé re-leyendo y aplicando `If-Match: <etag>`. `422 validation`: el body falla el schema; el detalle campo-por-campo viene en `error.fields`.

## SLA y status
Status page: status.nixcloud.example. Incidentes se comunican por el banner del dashboard y por webhook `incident.updated`. El SLA del plan Pro es 99.5% (medido mensualmente, excluye mantenimiento anunciado con 72 h). Créditos por SLA: se reclaman hasta 30 días después del mes afectado desde Billing → SLA credits.
