# Repository Rules

Before every commit:

- Review files for accidental secret exposure.
- Remove temporary files.
- Remove debugging code.
- Verify no credentials are included.

The repository MUST NOT contain:

- node_modules/
- build/
- dist/
- coverage/
- .env
- *.log
- *.zip
- Temporary files

Always use placeholders instead of real values in documentation.

Example:

<AWS_ACCOUNT_ID>
<BUCKET_NAME>
<API_KEY>
