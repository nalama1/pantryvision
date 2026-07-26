# Project Structure — PantryVision

/frontend  → React app (TypeScript)
/backend   → Lambda functions (Python 3.12)
/infra     → Amplify configuration
README.md  → title, description, problem it solves

## Code Conventions

### Backend (Python)

- Use snake_case for function names, variables, and file names (e.g., get_product(), expiration_date, upload_invoice_photo())
- Use PascalCase for class names
- Follow PEP 8 style guide
- Comments in English (explain the "why", not the "what")
- Use type hints where possible

### Frontend (React/TypeScript)

- Use camelCase for function names and variables (e.g., getProduct(), expirationDate, uploadInvoicePhoto())
- Use PascalCase for component names and interfaces
- Comments in English (explain the "why", not the "what")

### AWS Resources

- AWS resource names (buckets, DynamoDB tables, Lambda functions): kebab-case, all lowercase (e.g., pantryvision-product-images, upload-product-photo, products)

### General

- Small, descriptive commits in English

## Documentation Language

- Specs (requirements.md, design.md, tasks.md): in English, consistent with code
- Steering files (product.md, tech.md, structure.md): in English
- Code comments: in English
- README: in English
