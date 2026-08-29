# 📘 PantryVision — Resumen técnico completo

> Documento de referencia interna: arquitectura completa, servicios AWS, y decisiones de diseño del proyecto.

## 🎯 Objetivo del proyecto

Eliminar el desperdicio de alimentos y las compras duplicadas en el hogar, automatizando el registro del inventario mediante fotos y alertando proactivamente antes de que algo se venza — sin que el usuario tenga que anotar nada manualmente.

---

## 🏗️ Arquitectura completa, servicio por servicio

### 1. Frontend
- **React + TypeScript + Vite** — SPA con estado local (sin Redux); componentes: PhotoUploader, ReviewForm, InventoryDashboard, NavBar
- **AWS Amplify Hosting** — despliegue automático: cada `git push` a `main` dispara build (`npm run build`) y publica en producción en ~60-90s, vía webhook GitHub↔Amplify
- **i18n propio** (Context API + diccionario, sin librería externa) — ES/EN con cambio instantáneo
- **canvas-confetti** — micro-interacción de éxito al guardar un producto

### 2. Autenticación y seguridad (sin login tradicional)
- **Amazon Cognito Identity Pool** — acceso no autenticado pero con credenciales temporales y *scoped*; el frontend nunca guarda claves AWS permanentes
- **AWS Signature V4 (SigV4)** — cada request al API Gateway se firma con las credenciales temporales (librería `aws4fetch`)
- **API Gateway con `AuthorizationType: AWS_IAM`** — los 4 endpoints principales (upload, extract, save, list) exigen firma válida; solo el método `OPTIONS` (preflight CORS) queda sin auth

### 3. Flujo de subida y extracción con IA
- **Lambda `upload-product-photo`** (Python 3.12) — genera una URL prefirmada de S3 (`PUT`); el navegador sube la imagen directo a S3 sin pasar por Lambda (ahorra cómputo y costo)
- **Amazon S3 (bucket privado)** — almacena imágenes; acceso exclusivo vía URLs prefirmadas, nunca público
- **Lambda `extract-product-data`** — redimensiona la imagen a 1024px (reduce costo de tokens) y la envía a Amazon Bedrock
- **Amazon Bedrock — modelo Amazon Nova Pro** — recibe la imagen y extrae: nombre del producto, marca, presentación, fecha de vencimiento, con niveles de confianza por campo (alto/medio/bajo). `maxTokens` capado en 400 para controlar costo. Timeout de 30s.
  - *Decisión documentada: se probaron Nova Lite (alucinaba mucho), Claude 3.5/3 Haiku (problemas de acceso / perfil de inferencia), y se eligió Nova Pro por estabilidad y ausencia de alucinaciones.*
- **Fallback manual obligatorio** — si la IA falla o da baja confianza, el usuario completa los campos a mano; la IA nunca bloquea el flujo (principio de diseño explícito)

### 4. Revisión y guardado
- **ReviewForm** — el usuario confirma/edita los datos extraídos antes de guardar
- **Lambda `save-product`** — valida y escribe el registro en DynamoDB
- **Amazon DynamoDB** (tabla `pantryvision-products`, modo on-demand) — sin capacidad aprovisionada, paga solo por uso real

### 5. Inventario y visualización
- **Lambda `list-products`** — escanea DynamoDB, genera URLs prefirmadas de lectura para las imágenes, devuelve la lista completa
- **InventoryDashboard** — tarjetas con badges de color (verde = fresco, morado = por vencer, rojo = vencido), filtros por estado, diseño responsive

### 6. Alertas automáticas de vencimiento
- **Amazon EventBridge** — regla de cron diario (`cron(0 8 * * ? *)`, 8am UTC) que dispara la Lambda de alertas; también invocable manualmente para demos (`aws lambda invoke`)
- **Lambda `check-expiring-products`** — arquitectura de funciones puras + I/O separadas (SRP): `get_alert_config`, `scan_products` (con reintentos), `classify_products` (pura, testeable), `build_email_body` (pura, genera HTML), `send_alert_email`, `log_run_summary`
- **Amazon SES** (modo sandbox) — envía el correo HTML con tablas separadas por color (rojo/rosa para vencidos, morado/lila para por vencer), fechas relativas ("Jul 25 (Yesterday)", "In 4 days"), copy cálido en inglés
- **Amazon CloudWatch** — logging estructurado de conteos y estado de envío, sin PII ni credenciales en los logs (validado explícitamente como principio de diseño)

### 7. Infraestructura como código
- **7 templates de CloudFormation** en `/infra`: S3, DynamoDB, y una Lambda + API Gateway por cada función (upload, extract, save, list), más el stack de Cognito Identity Pool, más el stack de alertas — cada uno con roles IAM de mínimo privilegio (nunca permisos amplios tipo `*`)

---

## 🧪 Calidad y testing
- **38 tests unitarios** (pytest) en el módulo de alertas: clasificación, construcción de email, reintentos de SES/DynamoDB, logging seguro
- **Property-based testing** (Hypothesis) contemplado en el diseño (12 propiedades de corrección documentadas), parcialmente implementado — quedaron 19 tareas opcionales sin ejecutar por prioridad de tiempo
- **Metodología spec-driven con Kiro**: cada una de las 6 features pasó por `requirements.md → design.md → tasks.md` antes de escribir código, documentado en `.kiro/specs/`

---

## 💰 Principios de costo y arquitectura aplicados
- 100% *serverless* — cero EC2, cero RDS, cero servidores que mantener o parchear
- Pay-per-use en cada capa: Lambda (por invocación), DynamoDB on-demand (sin capacidad reservada), S3 (por almacenamiento/transferencia real)
- Imagen redimensionada antes de Bedrock → menos tokens → menos costo por extracción
- Subida directa a S3 (bypass de Lambda) → menos tiempo de cómputo facturado

---

## 🔑 Servicios AWS usados (lista rápida)

| # | Servicio | Rol en el proyecto |
|---|----------|--------------------|
| 1 | AWS Amplify Hosting | Hosting del frontend + CI/CD automático |
| 2 | AWS Lambda | 5 funciones (upload, extract, save, list, check-expiring) |
| 3 | Amazon API Gateway | 4 endpoints REST con autorización IAM |
| 4 | Amazon Cognito | Identity Pool, credenciales temporales |
| 5 | Amazon S3 | Imágenes privadas, URLs prefirmadas |
| 6 | Amazon Bedrock (Nova Pro) | Extracción de datos por IA de visión |
| 7 | Amazon DynamoDB | Inventario, modo on-demand |
| 8 | Amazon EventBridge | Cron diario de alertas |
| 9 | Amazon SES | Envío de correos de alerta |
| 10 | Amazon CloudWatch | Logs y observabilidad |

---

## 🔄 Flujo end-to-end (resumen)

1. Usuario toma/selecciona foto → frontend pide URL prefirmada (`upload-product-photo`) → sube directo a S3
2. Frontend llama a `extract-product-data` → Bedrock (Nova Pro) lee la imagen → devuelve datos + confianza
3. Usuario revisa/corrige en ReviewForm → `save-product` guarda en DynamoDB
4. `list-products` alimenta el InventoryDashboard con badges y filtros
5. Cada día, EventBridge dispara `check-expiring-products` → clasifica → SES envía el correo de alerta
6. Todas las requests van firmadas con SigV4 usando credenciales temporales de Cognito
