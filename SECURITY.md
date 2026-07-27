# Security Policy

## Supported Versions

This project does not maintain multiple versions; only the `main` branch is
supported. Fixes are applied directly to `main` and there are no maintained
release branches or backports.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately rather
than opening a public GitHub Issue. You can do so through GitHub's private
security advisory feature:

**https://github.com/nalama1/pantryvision/security/advisories/new**

Alternatively, you can reach the maintainer directly at
**<SECURITY_CONTACT_EMAIL>**.

Please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce it
- Any relevant logs, requests, or screenshots (with personal data redacted)

This is a solo-maintained project, so there's no dedicated security team.
Reports will be reviewed and addressed on a best-effort basis, but please
expect response times consistent with an individually maintained open
source project rather than a formal security program.

## Security Posture

PantryVision is built with the following security practices in mind:

- **Private storage**: Product images are stored in a private Amazon S3
  bucket. Access happens exclusively through presigned URLs, never through
  public bucket access.
- **Authorization on API endpoints**: API Gateway endpoints require AWS IAM
  authorization, using temporary, scoped credentials issued by an Amazon
  Cognito Identity Pool.
- **No hardcoded credentials**: The codebase does not contain AWS access
  keys, secrets, or other credentials. AWS resources use IAM roles, and
  frontend configuration uses environment variables.
- **Encryption**: Data is encrypted at rest (S3, DynamoDB) and in transit
  (HTTPS/TLS for all API and AWS service communication).
- **Least privilege IAM**: Each Lambda function's IAM role is scoped to the
  specific AWS resources and actions it needs.

## Known Limitations (Hackathon / Demo Project)

PantryVision was built as a hackathon/demo project and has some limitations
that would need to be addressed before handling real, sensitive data at
scale:

- **Amazon SES is in sandbox mode**, so email alerts are limited to
  verified recipients and are not suitable for production-scale delivery.
- **The Cognito Identity Pool grants unauthenticated access** (no login is
  required to use the app), meaning anyone with the deployed URL can create
  and view inventory data through the API.
- There is no per-user data isolation, rate limiting, or formal incident
  response process in place.

**Do not store real, sensitive, or personally identifiable data in this
deployment.** Treat any publicly deployed instance of PantryVision as a demo
environment rather than a production system.
