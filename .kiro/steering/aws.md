# AWS Service Guidelines

## Approved Services

The project SHALL use only the following AWS services unless explicitly approved:

- AWS Amplify Hosting
- AWS Lambda
- Amazon API Gateway
- Amazon DynamoDB (On-Demand)
- Amazon S3
- Amazon Bedrock
- Amazon EventBridge
- Amazon SES
- Amazon CloudWatch
- AWS IAM

## Services Not Allowed

- Amazon EC2
- Amazon RDS
- Amazon ECS / EKS
- Self-managed databases or servers

Reason: The project must remain fully serverless, cost-efficient, and simple to maintain.

## Cost Optimization

- Prefer pay-per-request pricing.
- Use DynamoDB On-Demand capacity mode.
- Avoid idle resources.
- Avoid unnecessary AI model invocations.
- Upload files directly to S3 using pre-signed URLs.
- Minimize the amount of data sent to Amazon Bedrock.
- Minimize prompt size whenever possible.

## Amazon DynamoDB

- Use On-Demand billing mode.
- Use a simple primary key design for the MVP.
- Avoid unnecessary GSIs and LSIs unless required.
- Store only metadata required by the application.
- Do not store image binaries.

## AWS Lambda

- Keep Lambda functions focused on a single responsibility.
- Minimize execution time.
- Handle exceptions gracefully.
- Return meaningful HTTP responses.
- Use environment variables for configuration.

## Amazon Bedrock

- Invoke AI models only when required.
- Send only the minimum information necessary.
- Require user confirmation before AI processing.
- Never include sensitive personal information in prompts.
- Validate AI output before persistence.
- Log AI errors without exposing user data.

## Monitoring

Use Amazon CloudWatch for:

- Application logs
- Error tracking
- Operational monitoring

Logs SHALL NOT contain credentials, secrets, personal data, or uploaded images.

## Infrastructure

- Manage infrastructure as code using CloudFormation templates.
- Store templates in the `/infra` directory.
- Prefer infrastructure changes through CloudFormation instead of manual changes in the AWS Console.

## Reliability

- Handle transient AWS failures gracefully.
- Retry recoverable operations when appropriate.
- Provide meaningful error messages.
- Fail securely.

## Future Scalability

Design every component assuming future growth. Prefer solutions that can scale horizontally without architectural redesign. Avoid introducing unnecessary complexity during the MVP.
