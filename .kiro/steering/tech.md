# Tech Stack — PantryVision

## Fixed (do not change without discussing first)

- Frontend: React
- Hosting: AWS Amplify Hosting
- Backend: AWS Lambda (Python 3.12), using boto3 for AWS service integration
- Database: Amazon DynamoDB (on-demand mode)
- Image Storage: Amazon S3 (private bucket)
- Data Extraction AI: Amazon Bedrock (Amazon Nova Pro)
- Alerts: Amazon SES + EventBridge (daily cron)
- Infrastructure: CloudFormation templates (stored in /infra)

## Architecture Rules

- Prefer 100% serverless architecture (pay-per-use) over dedicated servers like EC2 or RDS, for cost efficiency, less maintenance, and better automatic scalability.
- S3 buckets are always private; access only via presigned URLs
- Do not store sensitive information without encryption
- AI must never be a blocking requirement: if it cannot read a piece of data (e.g., blurry expiration date), the system must allow manual entry
- Never hardcode credentials, API keys, or secrets in source code. Use environment variables or IAM roles when resources run on AWS.

## Architecture Principles (AWS Well-Architected Framework)

- Cost Optimization: serverless architecture, pay-per-use
- Security: no hardcoded credentials, private buckets, IAM roles
- Reliability: AI never blocks the flow — there is always a manual fallback
