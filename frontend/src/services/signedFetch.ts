/**
 * Signed fetch wrapper for calling AWS_IAM-protected API Gateway endpoints.
 * Obtains temporary credentials from Cognito Identity Pool (see awsCredentials.ts)
 * and signs the request with AWS Signature V4 using aws4fetch.
 */
import { AwsClient } from 'aws4fetch';
import { getTemporaryCredentials } from './awsCredentials';

const REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1';

/**
 * Performs a signed fetch request to an API Gateway endpoint with AWS_IAM auth.
 * Behaves like the native fetch() but adds SigV4 signing headers automatically.
 */
export async function signedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const credentials = await getTemporaryCredentials();

  const client = new AwsClient({
    accessKeyId: credentials.accessKeyId,
    secretAccessKey: credentials.secretAccessKey,
    sessionToken: credentials.sessionToken,
    region: REGION,
    service: 'execute-api',
  });

  return client.fetch(url, options);
}
