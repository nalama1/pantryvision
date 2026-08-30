<a id="top"></a>
# 🥫 PantryVision

<p align="center">
  <a href="README.md">🇺🇸 English version</a>
</p>

Una aplicación web serverless para la gestión del inventario del hogar. Sube una foto de un producto y un modelo de IA de visión extrae el nombre, la marca, la presentación y la fecha de caducidad. Confirma los datos y el sistema los guarda en tu inventario personal, con alertas de caducidad y de bajo stock.

## Tabla de contenidos

- [🧩 Problema](#problem)
- [✨ Características](#features)
- [🏗️ Arquitectura](#architecture)
- [🛠️ Stack tecnológico](#tech-stack)
- [🛠️ Construido con](#built-with)
- [📁 Estructura del proyecto](#project-structure)
- [🚀 Primeros pasos](#getting-started)
- [📋 Referencia de AWS CLI y flujo de despliegue](#aws-cli-reference)
- [🗂️ Documentación interna (.kiro/)](#internal-documentation)
- [🔒 Seguridad](#security)
- [☁️ Alineación con AWS Well-Architected](#aws-well-architected-alignment)
- [🏆 Sobre este proyecto](#about-this-project)
- [📄 Licencia](#license)
- [🙌 Créditos](#credits)

<a id="problem"></a>
## 🧩 Problema

No existe un registro de qué se compró, cuándo y cuándo caduca. Esto provoca desperdicio por productos vencidos y compras duplicadas o tardías.

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="features"></a>
## ✨ Características

- **Carga de fotos** — Selecciona o captura la imagen de un producto (JPEG, PNG, WebP, máx. 5 MB)
- **Extracción de datos con IA** — Amazon Bedrock (Amazon Nova Pro) extrae el nombre del producto, la marca, la presentación y la fecha de caducidad
- **Alternativa manual** — Si la IA no puede leer los datos, el usuario puede introducirlos manualmente
- **Revisar y confirmar** — Formulario editable con indicadores de confianza antes de guardar
- **Panel de inventario** — Consulta, filtra (Caducado / Por caducar / Bien) y navega por los productos guardados con sus imágenes
- **Vista de tabla** — Un listado tipo hoja de cálculo que complementa las tarjetas: columnas claras (#, caducidad, nombre, marca, presentación, cantidad, estado, activo/inactivo, imagen), un filtro de estado, paginación del lado del cliente (5 / 10 / 20 filas por página con indicador de posición), una casilla opcional para "mostrar inactivos" que incluye los productos con borrado lógico, y un visor de imagen (lightbox) bajo demanda
- **Editar y eliminar (CRUD)** — Actualiza los datos de un producto o quítalo del inventario. La eliminación es un *borrado lógico* (el registro se marca, nunca se borra físicamente), con un diálogo de confirmación accesible y confirmación visual en línea
- **Alertas de caducidad** — Correo automático diario (Amazon EventBridge + SES) que lista los productos que caducan en un plazo de 7 días o que ya han caducado, con un resumen HTML claro
  - *Nota: Amazon SES opera en modo sandbox para esta demo (la configuración predeterminada para las cuentas nuevas de AWS), lo que restringe el envío únicamente a direcciones verificadas previamente. La funcionalidad es completa y ha sido probada de extremo a extremo — consulta el video de la demo para ver un ejemplo real del correo de alerta. En producción, se solicitaría el acceso a producción de SES para habilitar el envío a cualquier destinatario.*

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="architecture"></a>
## 🏗️ Arquitectura

PantryVision está construido íntegramente sobre AWS con una arquitectura 100% serverless y de pago por uso.

```
┌─────────────┐     ┌──────────────────┐
│   React     │────▶│ Cognito Identity │
│  (Frontend) │     │      Pool        │
└─────────────┘     └──────────────────┘
       │                     │
       │ SigV4-signed        │ temporary
       │ requests            │ credentials
       ▼                     │
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│ API Gateway │◀────┴─────────────┴────▶│  AWS Lambda      │
│  (REST)     │                         │  (Python 3.12)   │
└─────────────┘                         └──────────────────┘
                                               │       │
                                               ▼       ▼
                                         ┌─────────┐ ┌──────────┐
                                         │   S3    │ │ Bedrock  │
                                         │ (Images)│ │ (AI)     │
                                         └─────────┘ └──────────┘
                                               │
                                               ▼
                                         ┌──────────┐
                                         │ DynamoDB │
                                         │(Inventory│
                                         └──────────┘
```

![PantryVision Architecture Diagram](docs/architecture-diagram.png)

Las solicitudes a API Gateway se firman con AWS Signature V4 usando
credenciales temporales obtenidas de un Amazon Cognito Identity Pool (acceso
sin autenticación — no requiere inicio de sesión).

### Servicios de AWS utilizados

| Servicio | Propósito |
|---------|---------|
| AWS Amplify Hosting | Alojamiento del frontend |
| AWS Lambda | Funciones de backend (Python 3.12) |
| Amazon API Gateway | Endpoints de la API REST |
| Amazon DynamoDB | Base de datos del inventario de productos (on-demand) |
| Amazon S3 | Almacenamiento privado de imágenes |
| Amazon Bedrock | Modelo de IA de visión para la extracción de datos |
| Amazon EventBridge | Cron diario para las alertas |
| Amazon SES | Notificaciones por correo electrónico |
| Amazon CloudWatch | Monitoreo y registro de logs |
| Amazon Cognito | Identity Pool para credenciales de AWS temporales y acotadas (firma de solicitudes SigV4) |

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="tech-stack"></a>
## 🛠️ Stack tecnológico

| Capa | Tecnología |
|-------|-----------|
| Frontend | React, TypeScript, Vite |
| Backend | Python 3.12, boto3 |
| Base de datos | Amazon DynamoDB (on-demand) |
| Modelo de IA | Amazon Bedrock (Amazon Nova Pro) |
| Almacenamiento | Amazon S3 (privado) |
| Infraestructura | CloudFormation |

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="built-with"></a>
## 🛠️ Construido con

[![AWS](https://img.shields.io/badge/AWS-Serverless-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Nova%20Pro-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![AWS Lambda](https://img.shields.io/badge/AWS%20Lambda-Python%203.12-FF9900?logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/)
[![Amazon DynamoDB](https://img.shields.io/badge/Amazon%20DynamoDB-on--demand-4053D6?logo=amazondynamodb&logoColor=white)](https://aws.amazon.com/dynamodb/)
[![Amazon S3](https://img.shields.io/badge/Amazon%20S3-private-569A31?logo=amazons3&logoColor=white)](https://aws.amazon.com/s3/)
[![AWS Amplify](https://img.shields.io/badge/AWS%20Amplify-Hosting-FF9900?logo=awsamplify&logoColor=white)](https://aws.amazon.com/amplify/)
[![Kiro](https://img.shields.io/badge/Built%20with-Kiro%20AI-8B5CF6)](https://kiro.dev/)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="project-structure"></a>
## 📁 Estructura del proyecto

```
/frontend   → React app (TypeScript, Vite)
/backend    → Lambda functions (Python 3.12)
/infra      → CloudFormation templates
```

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="getting-started"></a>
## 🚀 Primeros pasos

### Requisitos previos

- Node.js 18+
- Python 3.12
- AWS CLI v2 (configurado con credenciales)
- Una cuenta de AWS con el acceso a modelos de Amazon Bedrock habilitado

### Frontend (desarrollo local)

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local with your API Gateway URLs
npm install
npm run dev
```

### Backend (pruebas)

```bash
cd backend/extract-product-data
pip install -r requirements.txt
pytest
```

### Despliegue

La infraestructura se gestiona como plantillas de CloudFormation en `/infra`. Despliega en orden:

1. `infra/s3-bucket.yaml` — Bucket de S3
2. `infra/dynamodb-products.yaml` — Tabla de productos de DynamoDB
3. `infra/lambda-upload.yaml` — Lambda de carga + API Gateway
4. `infra/lambda-extract.yaml` — Lambda de extracción + API Gateway
5. `infra/lambda-save-product.yaml` — Lambda de guardado de producto + API Gateway
6. `infra/lambda-list-products.yaml` — Lambda de listado de productos + API Gateway
7. `infra/lambda-manage-products.yaml` — Lambdas de gestión de productos (edición + borrado lógico) + API Gateway
8. `infra/cognito-identity-pool.yaml` — Cognito Identity Pool (se despliega al final, necesita los 5 IDs de API Gateway como parámetros)

```bash
aws cloudformation deploy --template-file infra/s3-bucket.yaml --stack-name pantryvision-s3-bucket --region <AWS_REGION>
aws cloudformation deploy --template-file infra/dynamodb-products.yaml --stack-name pantryvision-dynamodb --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-upload.yaml --stack-name pantryvision-lambda-upload --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-extract.yaml --stack-name pantryvision-lambda-extract --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-save-product.yaml --stack-name pantryvision-lambda-save --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-list-products.yaml --stack-name pantryvision-lambda-list --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-manage-products.yaml --stack-name pantryvision-lambda-manage --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
aws cloudformation deploy --template-file infra/cognito-identity-pool.yaml --stack-name pantryvision-cognito-identity --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION> --parameter-overrides UploadApiId=<UPLOAD_API_ID> ExtractApiId=<EXTRACT_API_ID> SaveApiId=<SAVE_API_ID> ListApiId=<LIST_API_ID> ManageApiId=<MANAGE_API_ID>
```

### Variables de entorno

#### Frontend (`frontend/.env.local`)

```
VITE_API_ENDPOINT=<API_GATEWAY_UPLOAD_URL>
VITE_EXTRACT_API_ENDPOINT=<API_GATEWAY_EXTRACT_URL>
VITE_SAVE_API_ENDPOINT=<API_GATEWAY_SAVE_URL>
VITE_LIST_API_ENDPOINT=<API_GATEWAY_LIST_URL>
VITE_MANAGE_API_ENDPOINT=<API_GATEWAY_MANAGE_URL>
VITE_AWS_REGION=<AWS_REGION>
VITE_COGNITO_IDENTITY_POOL_ID=<COGNITO_IDENTITY_POOL_ID>
```

#### Backend (definidas por CloudFormation)

| Variable | Descripción |
|----------|-------------|
| `BUCKET_NAME` | Bucket de S3 para las imágenes de productos |
| `BEDROCK_MODEL_ID` | Identificador del modelo de Bedrock |
| `BEDROCK_TIMEOUT` | Tiempo de espera en segundos para la invocación de la IA |
| `TABLE_NAME` | Tabla de DynamoDB para el inventario de productos |

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="aws-cli-reference"></a>
## 📋 Referencia de AWS CLI y flujo de despliegue

Referencia rápida de los comandos de AWS CLI más utilizados al construir y operar PantryVision.

### Comandos de AWS CLI más usados

| N.º | Comando / Acción | Acción / Descripción |
|-----|-------------------|------------------------|
| 1 | `aws cloudformation deploy` | Despliega o actualiza un stack de CloudFormation (Lambdas, roles de IAM, API Gateway, EventBridge, Cognito) |
| 2 | `aws cloudformation describe-stacks` | Consulta el estado de un stack (p. ej. `CREATE_COMPLETE`) |
| 3 | `aws s3 cp` | Sube un `.zip` empaquetado de Lambda al bucket de despliegue de S3 |
| 4 | `aws lambda update-function-code` | Actualiza el código de una Lambda desplegada directamente, sin volver a ejecutar todo el stack de CloudFormation |
| 5 | `aws lambda invoke` | Invoca una Lambda manualmente (p. ej. probar `check-expiring-products` sin esperar a su programación diaria) |
| 6 | `aws lambda get-function` | Consulta el estado de una Lambda (`LastUpdateStatus`, runtime, handler) |
| 7 | `aws logs tail` | Transmite los CloudWatch Logs en tiempo real (p. ej. confirmar el log `run_summary` tras invocar una Lambda) |
| 8 | `aws ses verify-email-identity` | Verifica una dirección de correo como identidad de SES (requerido en modo sandbox) |
| 9 | `aws ses get-identity-verification-attributes` | Confirma si una identidad de SES completó la verificación |
| 10 | `aws amplify list-apps` / `list-branches` / `list-jobs` | Consulta las apps, ramas y trabajos de compilación de Amplify Hosting (revisar los auto-despliegues) |
| 11 | `aws sts get-caller-identity` | Confirma la cuenta/rol de AWS activo en la sesión actual de la CLI (buena práctica antes de desplegar) |
| 12 | `aws configure` | Configura las credenciales y la región predeterminadas de la CLI |

### Flujo de despliegue: `git push` → auto-despliegue de Amplify

| Paso | Comando / Acción | Qué ocurre |
|------|-------------------|--------------|
| 1 | `git add <files>` | Prepara solo los archivos relevantes del cambio (nunca un `git add .` a ciegas) |
| 2 | `git commit -m "descriptive message"` | Crea el commit local con un mensaje claro en inglés |
| 3 | `git push` | El commit se envía a la rama `main` en GitHub |
| 4 | *(automático)* Amplify detecta el push | AWS Amplify Hosting tiene un webhook conectado al repositorio — cualquier push a `main` lo dispara, sin pasos manuales |
| 5 | *(automático)* Amplify ejecuta la compilación | Ejecuta `npm run build` dentro de `/frontend` (según la configuración de monorepo en Amplify) |
| 6 | *(automático)* Amplify despliega la nueva versión | Si la compilación tiene éxito, la nueva versión se publica en `https://main.<app-id>.amplifyapp.com` en ~60-90 segundos |
| 7 | `aws amplify list-jobs --app-id <ID> --branch-name main` | *(Opcional)* Consulta el estado de la última compilación (`SUCCEED`/`FAILED`) desde la CLI sin abrir la consola |
| 8 | Verificación manual en el navegador/móvil | Abre la URL de Amplify para confirmar visualmente que el cambio llegó a producción |

**Punto clave**: los pasos 4-6 son totalmente automáticos — Amplify Hosting vigila la rama `main` del repositorio de GitHub, por lo que ningún comando de AWS CLI dispara directamente el despliegue; simplemente ocurre como consecuencia del `git push`.

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="internal-documentation"></a>
## 🗂️ Documentación interna (.kiro/)

PantryVision se construyó usando el flujo de trabajo basado en especificaciones de [Kiro](https://kiro.dev/). Cada funcionalidad pasó por un ciclo `requirements.md → design.md → tasks.md` antes de la implementación, y las convenciones del proyecto están codificadas como archivos de steering para que el agente de IA se mantuviera consistente durante toda la construcción. Esta documentación interna vive en `.kiro/` y forma parte del repositorio.

```
.kiro/
├── specs/
│   ├── upload-product-photo/       -- Photo capture, validation, presigned S3 upload
│   ├── ai-data-extraction/         -- Amazon Bedrock (Nova Pro) extraction pipeline
│   ├── save-product-inventory/     -- Save confirmed product data to DynamoDB
│   ├── inventory-dashboard/        -- List, filter, and display saved products
│   ├── manage-products/            -- Update + soft-delete products (CRUD)
│   ├── frontend-ui-redesign/       -- Visual redesign, i18n (ES/EN), UX polish
│   ├── expiration-alerts/          -- Daily EventBridge + SES expiration email
│   └── product-table-view/         -- Spreadsheet-style table: filter, pagination, image lightbox, show-inactive
│       (each spec: requirements.md, design.md, tasks.md)
│
└── steering/
    ├── product.md              -- Product context, target audience, key objectives
    ├── tech.md                 -- Fixed tech stack & architecture rules (serverless-first, AI never blocks, no hardcoded secrets)
    ├── structure.md            -- Project layout and code conventions
    ├── aws.md                  -- Approved AWS services & cost optimization guidelines
    ├── security.md             -- Secrets management & sensitive data handling
    ├── best-practices.md       -- AWS Well-Architected best practices
    └── repository.md           -- Pre-commit checklist & repo exclusion rules
```

Cada especificación documenta los criterios de aceptación (formato EARS), el diseño técnico y el desglose de tareas que realmente se ejecutó. Esto mantuvo el contexto del agente de IA consistente desde el primer flujo de carga hasta el rediseño final de la interfaz, sin tener que reexplicar las reglas del proyecto en cada conversación.

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="security"></a>
## 🔒 Seguridad

- Todos los buckets de S3 son privados — acceso únicamente mediante URLs prefirmadas
- Los endpoints de la API usan autorización de AWS IAM
- No hay credenciales embebidas en el código fuente
- Datos cifrados en reposo y en tránsito
- Principio de mínimo privilegio aplicado a todos los roles de IAM
- Los visitantes anónimos reciben credenciales de AWS temporales y acotadas a través de un Cognito Identity Pool (sin claves de larga duración expuestas en el código del frontend)

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="aws-well-architected-alignment"></a>
## ☁️ Alineación con AWS Well-Architected

| Pilar | Cómo lo aplica PantryVision |
|--------|----------------------------|
| Seguridad | Buckets de S3 privados, autorización IAM en todos los endpoints, roles de IAM con mínimo privilegio, cifrado en reposo y en tránsito |
| Optimización de costos | Serverless de pago por uso, DynamoDB on-demand, imagen redimensionada a 1024px antes de invocar Bedrock, maxTokens limitado a 400 |
| Fiabilidad | La IA nunca bloquea el flujo del usuario — siempre hay una alternativa manual disponible, manejo elegante de errores en todas las llamadas a servicios de AWS |
| Eficiencia del rendimiento | Imagen reducida antes del procesamiento con IA, tiempos de espera de Lambda configurados por función, timeout de Bedrock en 30s |
| Excelencia operativa | Infraestructura como código (CloudFormation), registro estructurado en CloudWatch con métricas de duración y tokens |
| Sostenibilidad | Serverless escala a cero (sin recursos inactivos), imagen redimensionada antes de la IA para reducir el cómputo, cargas directas a S3 que evitan Lambda, salida de tokens limitada |

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="about-this-project"></a>
## 🏆 Sobre este proyecto

PantryVision se desarrolló como parte del Kiro Hackathon, organizado por
Código Facilito en colaboración con AWS y Kiro AI.

### Aspectos destacados

- 🚀 Construido durante un sprint intensivo de desarrollo de 6 días
- 👩‍💻 Diseñado e implementado de forma individual
- ☁️ Construido con servicios serverless de AWS
- 🤖 Usa Amazon Bedrock para extraer información de productos a partir de imágenes
- 📱 Aplicación web responsiva desplegada en AWS Amplify
- 🎯 Creado para ayudar a reducir el desperdicio de alimentos en el hogar mediante el seguimiento de las fechas de caducidad de los productos

### 🤖 Sobre Kiro

Este proyecto se construyó usando [Kiro](https://kiro.dev/), un entorno de
desarrollo (IDE) impulsado por IA que ayudó a diseñar, implementar y documentar
PantryVision a través de un flujo de trabajo estructurado y basado en especificaciones.

| Aspecto | Descripción |
|--------|--------------|
| **Qué es Kiro** | Un IDE de IA agéntica (basado en VS Code) que empareja a un desarrollador con un agente de IA para planificar, escribir y verificar código — no solo autocompletarlo. |
| **Flujo de trabajo principal** | Desarrollo basado en especificaciones: requisitos → diseño → tareas → implementación, de modo que las funcionalidades se planifican y revisan antes de escribir código. |
| **Modo Vibe** | Programación conversacional y exploratoria para iteraciones rápidas, prototipado y pequeñas correcciones sin una especificación formal. |
| **Modo Spec** | Flujo de trabajo estructurado que genera `requirements.md`, `design.md` y `tasks.md` para una funcionalidad, manteniendo la documentación y el código sincronizados. |
| **Archivos de steering** | Archivos de contexto a nivel de proyecto (`.kiro/steering/`) que codifican convenciones, decisiones sobre el stack tecnológico y contexto del producto para que el agente se mantenga consistente entre sesiones. |
| **Agent Hooks** | Automatizaciones que disparan acciones del agente ante eventos (guardado de archivos, finalización de tareas, etc.), usadas para mantener consistentes los controles de calidad. |
| **Pruebas basadas en propiedades** | Kiro fomenta definir propiedades de correctitud y validarlas con pruebas generativas, no solo pruebas unitarias basadas en ejemplos. |
| **Uso en PantryVision** | Planificar funcionalidades (carga de fotos, extracción con IA, panel de inventario, alertas de caducidad), generar y refactorizar código tanto de backend (Python) como de frontend (React/TypeScript), escribir pruebas y mantener esta documentación. |

Este proyecto se creó como un MVP para un hackathon y representa una prueba de
concepto funcional. Las mejoras futuras podrían incluir autenticación,
notificaciones push, escaneo de códigos de barras y analítica avanzada del inventario.

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="license"></a>
## 📄 Licencia

MIT

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>

<a id="credits"></a>
## 🙌 Créditos

Este proyecto se originó en el Hackathon de Inteligencia Artificial con Kiro (organizado por Código Facilito con el apoyo de AWS), que se llevó a cabo hasta el 27 de julio de 2026. Desde entonces, el desarrollo ha continuado de forma independiente.

<p align="right"><a href="#top">⬆️ Volver arriba</a></p>
