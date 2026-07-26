# Security Guidelines

## Secrets Management

Never commit or expose:

- AWS Access Keys
- AWS Secret Access Keys
- Session Tokens
- .env files
- API keys
- Database passwords
- SMTP credentials
- Private keys (.pem, .key, .p12)
- SSH keys
- OAuth secrets
- JWT signing secrets
- GitHub Personal Access Tokens

## Sensitive Data

Never commit:

- User uploaded images
- Personally Identifiable Information (PII)
- Customer data
- CloudWatch logs containing sensitive information

## AWS Resources

- S3 buckets must remain private.
- Use pre-signed URLs for uploads.
- Enable encryption at rest.
- Use HTTPS for all communications.
- Follow the Principle of Least Privilege.
