/**
 * Provides temporary AWS credentials via a Cognito Identity Pool with
 * unauthenticated (anonymous) access. This allows the frontend to sign
 * requests with AWS Signature V4 for AWS_IAM-protected API Gateway endpoints,
 * without requiring a login/signup flow.
 *
 * Credentials are short-lived (typically 1 hour) and scoped to the
 * `execute-api:Invoke` permission only — see /infra/cognito-identity-pool.yaml.
 */
import {
  CognitoIdentityClient,
  GetIdCommand,
  GetCredentialsForIdentityCommand,
} from '@aws-sdk/client-cognito-identity';

export interface TemporaryCredentials {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken: string;
}

let cachedCredentials: TemporaryCredentials | null = null;
let cachedExpiration: Date | null = null;

const REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';
const IDENTITY_POOL_ID = import.meta.env.VITE_COGNITO_IDENTITY_POOL_ID;

/**
 * Returns cached temporary credentials if still valid, otherwise fetches new ones
 * from the Cognito Identity Pool. Refreshes automatically 5 minutes before expiration.
 */
export async function getTemporaryCredentials(): Promise<TemporaryCredentials> {
  const now = new Date();
  const bufferMs = 5 * 60 * 1000; // refresh 5 min before actual expiration

  if (cachedCredentials && cachedExpiration && cachedExpiration.getTime() - bufferMs > now.getTime()) {
    return cachedCredentials;
  }

  if (!IDENTITY_POOL_ID) {
    throw new Error('Cognito Identity Pool not configured. Set VITE_COGNITO_IDENTITY_POOL_ID environment variable.');
  }

  const client = new CognitoIdentityClient({ region: REGION });

  const { IdentityId } = await client.send(
    new GetIdCommand({ IdentityPoolId: IDENTITY_POOL_ID }),
  );

  if (!IdentityId) {
    throw new Error('Failed to obtain Cognito identity ID.');
  }

  const { Credentials } = await client.send(
    new GetCredentialsForIdentityCommand({ IdentityId }),
  );

  if (!Credentials?.AccessKeyId || !Credentials?.SecretKey || !Credentials?.SessionToken) {
    throw new Error('Failed to obtain temporary AWS credentials from Cognito.');
  }

  cachedCredentials = {
    accessKeyId: Credentials.AccessKeyId,
    secretAccessKey: Credentials.SecretKey,
    sessionToken: Credentials.SessionToken,
  };
  cachedExpiration = Credentials.Expiration ?? new Date(now.getTime() + 55 * 60 * 1000);

  return cachedCredentials;
}
