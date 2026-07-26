"""Unit tests for retrieve_image function."""

import os
import io
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError

# Set a dummy region so module-level boto3 clients can initialize during import
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from handler import retrieve_image


class TestRetrieveImage:
    """Tests for the retrieve_image function."""

    @patch("handler.s3_client")
    def test_returns_image_bytes_and_format_jpeg(self, mock_s3):
        """Should return (bytes, 'jpeg') for a .jpeg file."""
        fake_body = MagicMock()
        fake_body.read.return_value = b"fake-image-data"
        mock_s3.get_object.return_value = {"Body": fake_body}

        object_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpeg"
        result = retrieve_image(object_key)

        assert result is not None
        image_bytes, image_format = result
        assert image_bytes == b"fake-image-data"
        assert image_format == "jpeg"
        mock_s3.get_object.assert_called_once_with(
            Bucket="pantryvision-product-images", Key=object_key
        )

    @patch("handler.s3_client")
    def test_maps_jpg_to_jpeg(self, mock_s3):
        """Should map 'jpg' extension to 'jpeg' for Bedrock compatibility."""
        fake_body = MagicMock()
        fake_body.read.return_value = b"image-data"
        mock_s3.get_object.return_value = {"Body": fake_body}

        object_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
        result = retrieve_image(object_key)

        assert result is not None
        _, image_format = result
        assert image_format == "jpeg"

    @patch("handler.s3_client")
    def test_returns_png_format(self, mock_s3):
        """Should return 'png' format for .png files."""
        fake_body = MagicMock()
        fake_body.read.return_value = b"png-data"
        mock_s3.get_object.return_value = {"Body": fake_body}

        object_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890.png"
        result = retrieve_image(object_key)

        assert result is not None
        _, image_format = result
        assert image_format == "png"

    @patch("handler.s3_client")
    def test_returns_webp_format(self, mock_s3):
        """Should return 'webp' format for .webp files."""
        fake_body = MagicMock()
        fake_body.read.return_value = b"webp-data"
        mock_s3.get_object.return_value = {"Body": fake_body}

        object_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890.webp"
        result = retrieve_image(object_key)

        assert result is not None
        _, image_format = result
        assert image_format == "webp"

    @patch("handler.s3_client")
    def test_returns_none_on_no_such_key(self, mock_s3):
        """Should return None when the object does not exist in S3."""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

        object_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
        result = retrieve_image(object_key)

        assert result is None

    @patch("handler.s3_client")
    def test_raises_on_other_client_error(self, mock_s3):
        """Should re-raise ClientError for non-NoSuchKey errors (e.g., access denied)."""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

        object_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890.png"
        with pytest.raises(ClientError) as exc_info:
            retrieve_image(object_key)

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
