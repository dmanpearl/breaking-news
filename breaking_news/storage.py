"""
Custom Cloudinary storage backend.

Cloudinary has three resource types:
  image  — for raster/vector images (PNG, JPG, GIF, WEBP, SVG, …)
  raw    — for arbitrary binary files (PDF, CSV, ZIP, …)
  video  — for video/audio

django-cloudinary-storage's MediaCloudinaryStorage defaults to `image` for
everything.  Uploading a PDF as `image` causes two problems:

  1. Cloudinary rejects the upload with "Invalid image file" (or silently
     stores it in a broken state depending on account settings).
  2. The stored URL path is  …/image/upload/…  which Cloudinary refuses to
     serve for non-image content, returning 401 Unauthorized.

This backend overrides _get_resource_type() — a hook explicitly provided for
this purpose — to return 'raw' for PDF files and 'image' for everything else.
The correct resource type is then used for upload, URL generation, AND deletion,
so the entire lifecycle is consistent.
"""

import os

from cloudinary_storage.storage import MediaCloudinaryStorage

# File extensions that must be stored as Cloudinary 'raw' resources.
# Everything else uses the default 'image' resource type.
_RAW_EXTENSIONS = {".pdf"}


class SmartMediaCloudinaryStorage(MediaCloudinaryStorage):
    """MediaCloudinaryStorage that picks resource_type from the file extension."""

    def _get_resource_type(self, name: str) -> str:
        ext = os.path.splitext(name)[1].lower()
        if ext in _RAW_EXTENSIONS:
            return "raw"
        return "image"
