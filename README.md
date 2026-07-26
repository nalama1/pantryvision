# PantryVision

A serverless web application for household inventory management. Upload a photo of a product, and a vision AI model extracts the name, brand, presentation, and expiration date. Confirm the data, and the system saves it to your personal inventory with expiration and low-stock alerts.

## Problem

There is no record of what was purchased, when, and when it expires. This leads to waste from expired products and duplicate or late purchases.

## Demo

> Live URL: `<DEMO_URL>` *(coming soon)*

## Architecture

PantryVision is built entirely on AWS using a 100% serverless, pay-per-use architecture.

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   React     │────▶│ API Gateway │────▶│  AWS Lambda      │
│  (Frontend) │     │  (REST)     │     │  (Python 3.12)   │
└─────────────┘     └─────────────┘     └──────────────────┘
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

### AWS Services Used

| Service | Purpose |
|---------|---------|
| AWS Amplify Hosting | Frontend hosting |
| AWS Lambda | Backend functions (Python 3.12) |
| Amazon API Gateway | REST API endpoints |
| Amazon DynamoDB | Product inventory database (on-demand) |
| Amazon S3 | Private image storage |
| Amazon Bedrock | AI vision model for data extraction |
| Amazon EventBridge | Daily cron for alerts |
| Amazon SES | Email notifications |
| Amazon CloudWatch | Monitoring and logging |

## Features

- **Photo Upload** — Select or capture a product image (JPEG, PNG, WebP, max 5 MB)
- **AI Data Extraction** — Amazon Bedrock (Amazon Nova Pro) extracts product name, brand, presentation, and expiration date
- **Manual Fallback** — If AI cannot read the data, the user can enter it manually
- **Review & Confirm** — Editable form with confidence indicators before saving
- **Expiration Alerts** — Email notifications 7 days before products expire
- **Low-Stock Alerts** — Notifications when inventory is running low

## Project Structure

```
/frontend   → React app (TypeScript, Vite)
/backend    → Lambda functions (Python 3.12)
/infra      → CloudFormation templates
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.12
- AWS CLI v2 (configured with credentials)
- An AWS account with Amazon Bedrock model access enabled

### Frontend (local development)

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local with your API Gateway URLs
npm install
npm run dev
```

### Backend (tests)

```bash
cd backend/extract-product-data
pip install -r requirements.txt
pytest
```

### Deployment

Infrastructure is managed as CloudFormation templates in `/infra`. Deploy in order:

1. `infra/s3-bucket.yaml` — S3 bucket
2. `infra/lambda-upload.yaml` — Upload Lambda + API Gateway
3. `infra/lambda-extract.yaml` — Extraction Lambda + API Gateway

```bash
aws cloudformation deploy --template-file infra/s3-bucket.yaml --stack-name pantryvision-s3-bucket --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-upload.yaml --stack-name pantryvision-lambda-upload --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
aws cloudformation deploy --template-file infra/lambda-extract.yaml --stack-name pantryvision-lambda-extract --capabilities CAPABILITY_NAMED_IAM --region <AWS_REGION>
```

### Environment Variables

#### Frontend (`frontend/.env.local`)

```
VITE_API_ENDPOINT=<API_GATEWAY_UPLOAD_URL>
VITE_EXTRACT_API_ENDPOINT=<API_GATEWAY_EXTRACT_URL>
```

#### Backend (set by CloudFormation)

| Variable | Description |
|----------|-------------|
| `BUCKET_NAME` | S3 bucket for product images |
| `BEDROCK_MODEL_ID` | Bedrock model identifier |
| `BEDROCK_TIMEOUT` | Timeout in seconds for AI invocation |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite |
| Backend | Python 3.12, boto3 |
| Database | Amazon DynamoDB (on-demand) |
| AI Model | Amazon Bedrock (Amazon Nova Pro) |
| Storage | Amazon S3 (private) |
| Infrastructure | CloudFormation |

## Security

- All S3 buckets are private — access only via presigned URLs
- API endpoints use AWS IAM authorization
- No credentials are hardcoded in source code
- Data encrypted at rest and in transit
- Principle of Least Privilege applied to all IAM roles

## AWS Well-Architected Alignment

| Pillar | How PantryVision applies it |
|--------|----------------------------|
| Security | Private S3 buckets, IAM authorization on all endpoints, least privilege IAM roles, encryption at rest and in transit |
| Cost Optimization | Serverless pay-per-use, DynamoDB on-demand, image resized to 1024px before Bedrock invocation, maxTokens capped at 400 |
| Reliability | AI never blocks the user flow — manual fallback always available, graceful error handling on all AWS service calls |
| Performance Efficiency | Image downscaled before AI processing, Lambda timeouts configured per function, Bedrock timeout at 30s |
| Operational Excellence | Infrastructure as code (CloudFormation), structured CloudWatch logging with duration and token metrics |
| Sustainability | Serverless scales to zero (no idle resources), image resized before AI to reduce compute, direct-to-S3 uploads bypass Lambda, capped token output |

## License

MIT
