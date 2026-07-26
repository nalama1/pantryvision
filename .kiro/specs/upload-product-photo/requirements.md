# Requirements Document

## Introduction

This feature enables users to upload a product photo from their browser (selecting from gallery or capturing with camera) and store it securely in a private S3 bucket. The system uses presigned URLs to handle the upload without exposing AWS credentials to the frontend, and returns an S3 object key that can be referenced later for AI-based product data extraction.

## Glossary

- **Frontend**: The React web application running in the user's browser, hosted on AWS Amplify Hosting.
- **Upload_API**: The AWS Lambda function (Python 3.12) that generates presigned URLs for uploading images to S3.
- **Image_Store**: The private Amazon S3 bucket (`pantryvision-product-images`) used to store product photos.
- **Presigned_URL**: A time-limited URL generated server-side that grants temporary permission to upload a specific object to S3 without exposing credentials.
- **Object_Key**: The unique identifier (path/filename) assigned to an uploaded image in the Image_Store.
- **Photo_Uploader**: The frontend component responsible for capturing or selecting a photo and uploading it to S3 via a Presigned_URL.

## Requirements

### Requirement 1: Photo Capture and Selection

**User Story:** As a user, I want to select a photo from my device gallery or take a new photo with my camera, so that I can upload a product image without needing a separate app.

#### Acceptance Criteria

1. THE Photo_Uploader SHALL allow the user to select an image file from the device file system.
2. IF the device has camera access available, THEN THE Photo_Uploader SHALL allow the user to capture a new photo using the device camera.
3. THE Photo_Uploader SHALL accept only image files with MIME types `image/jpeg`, `image/png`, or `image/webp`.
4. WHEN the user selects a file that is not an accepted image type, THE Photo_Uploader SHALL display an error message indicating the accepted formats and SHALL NOT proceed with the upload flow.
5. WHEN the user selects an image file larger than 5 MB, THE Photo_Uploader SHALL display an error message indicating the maximum allowed file size of 5 MB and SHALL NOT proceed with the upload flow.
6. IF camera access is denied by the user or unavailable on the device, THEN THE Photo_Uploader SHALL hide the camera capture option and SHALL keep the file selection option available.
7. WHEN the user cancels the file selection or camera capture without choosing an image, THE Photo_Uploader SHALL remain in its initial state without displaying an error.
8. THE Photo_Uploader SHALL accept only image files with a minimum resolution of 200x200 pixels and a maximum resolution of 4096x4096 pixels.

### Requirement 2: Presigned URL Generation

**User Story:** As a developer, I want the backend to generate presigned URLs for S3 uploads, so that the frontend can upload images directly to S3 without exposing AWS credentials.

#### Acceptance Criteria

1. WHEN the Frontend requests a presigned URL providing the content type and the original file extension, THE Upload_API SHALL generate a presigned PUT URL for the Image_Store and return both the presigned URL and the generated Object_Key in the response.
2. THE Upload_API SHALL generate a unique Object_Key for each upload request using the format `{uuid-v4}.{original-extension}` where the extension is one of `jpeg`, `png`, or `webp`.
3. THE Upload_API SHALL set the presigned URL expiration time to 300 seconds (5 minutes).
4. THE Upload_API SHALL restrict the presigned URL to accept only the content type specified in the request.
5. THE Upload_API SHALL authenticate the request using IAM-based authorization before generating a presigned URL.
6. IF the authentication of the request fails, THEN THE Upload_API SHALL return an HTTP 401 response with an error message indicating the authentication failure reason.
7. IF the Upload_API fails to generate a presigned URL due to an internal error, THEN THE Upload_API SHALL return an HTTP 500 response with an error message indicating the failure reason.
8. IF the Frontend request is missing the content type or the file extension parameter, THEN THE Upload_API SHALL return an HTTP 400 response with an error message indicating the missing parameters.

### Requirement 3: Image Upload to S3

**User Story:** As a user, I want my product photo to be uploaded securely to cloud storage, so that it is safely stored and available for AI processing.

#### Acceptance Criteria

1. WHEN the Frontend receives a valid presigned URL, THE Photo_Uploader SHALL upload the selected image file directly to the Image_Store using an HTTP PUT request with the Content-Type header matching the file's MIME type.
2. WHEN the upload completes successfully, THE Photo_Uploader SHALL display a success confirmation to the user.
3. WHEN the upload completes successfully, THE Photo_Uploader SHALL return the Object_Key to the calling component for subsequent processing.
4. IF the upload fails due to network error, THEN THE Photo_Uploader SHALL display an error message and allow the user to retry the upload, up to a maximum of 3 retry attempts.
5. IF the presigned URL has expired, THEN THE Photo_Uploader SHALL request a new presigned URL from the Upload_API and retry the upload automatically once.
6. IF the automatic presigned URL retry also fails, THEN THE Photo_Uploader SHALL display an error message indicating the upload could not be completed and allow the user to initiate a new upload manually.
7. WHILE the upload is in progress, THE Photo_Uploader SHALL display a progress indicator to the user.
8. IF the upload does not complete within 30 seconds, THEN THE Photo_Uploader SHALL abort the request, display a timeout error message, and allow the user to retry.

### Requirement 4: Security and Access Control

**User Story:** As a system administrator, I want image uploads to follow security best practices, so that user data remains private and the system is not vulnerable to unauthorized access.

#### Acceptance Criteria

1. THE Image_Store SHALL deny all public access to stored objects.
2. THE Upload_API SHALL use IAM role credentials scoped to the minimum required permissions (PutObject on the Image_Store bucket only) to interact with the Image_Store.
3. THE Upload_API SHALL NOT include AWS credentials (access keys, secret keys, or session tokens) in any response sent to the Frontend.
4. WHEN the Frontend requests a presigned URL, THE Upload_API SHALL validate that the requested content type is one of `image/jpeg`, `image/png`, or `image/webp` before generating the URL.
5. IF the requested content type is not an allowed MIME type (`image/jpeg`, `image/png`, or `image/webp`), THEN THE Upload_API SHALL return an HTTP 400 response with an error message indicating the allowed content types.
6. THE Upload_API SHALL enforce a maximum content length of 5 MB in the presigned URL conditions.
7. THE Upload_API SHALL scope each presigned URL to a single, unique Object_Key so that the URL cannot be used to overwrite other stored objects.
8. THE Image_Store SHALL restrict CORS allowed origins to the Frontend domain only.

### Requirement 5: Image Preview

**User Story:** As a user, I want to see a preview of my selected photo before uploading, so that I can confirm it is the correct image.

#### Acceptance Criteria

1. WHEN the user selects or captures a photo, THE Photo_Uploader SHALL display a preview of the image at a minimum size of 200x200 pixels, maintaining the original aspect ratio, within 1 second of selection.
2. WHILE the preview is displayed, THE Photo_Uploader SHALL provide a cancel option that, when activated, removes the preview and returns the interface to the initial photo selection state without retaining any data from the previous selection.
3. WHEN the user activates the confirm action on the preview, THE Photo_Uploader SHALL disable the confirm and cancel options, and initiate the presigned URL request and subsequent upload as defined in Requirement 3.
4. IF the selected image cannot be rendered as a preview, THEN THE Photo_Uploader SHALL display an error message indicating the file could not be previewed and allow the user to select a different image.
