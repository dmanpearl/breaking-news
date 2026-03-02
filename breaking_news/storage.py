"""
Custom Cloudinary storage backend.

Cloudinary has three resource types:
  image  — for raster/vector images (PNG, JPG, GIF, WEBP, SVG, ...)
  raw    — for arbitrary binary files (PDF, CSV, ZIP, ...)
  video  — for video/audio

django-cloudinary-storage's MediaCloudinaryStorage defaults to `image` for
everything.  Uploading a PDF as `image` causes two problems:

  1. Cloudinary rejects the upload with "Invalid image file".
  2. The stored URL path is .../image/upload/... which returns 401 for
     non-image content.

This backend fixes the full lifecycle:

  _get_resource_type()  — 'raw' for PDFs, 'image' for everything else.
                          Used for upload, URL generation, and deletion.

  _upload()             — adds access_mode='public' for raw uploads so
                          future CDN fetches work without credentials.

  _open()               — downloads via the Cloudinary Admin API endpoint
                          (api.cloudinary.com) using HMAC-signed credentials
                          instead of a plain CDN GET. This works for ALL
                          resources regardless of access_mode or plan level,
                          and is the fallback used by field.read() in
                          services.py.
"""

import os

import cloudinary
import cloudinary.utils
import requests
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.core.files.base import ContentFile

_RAW_EXTENSIONS = {".pdf"}


class SmartMediaCloudinaryStorage(MediaCloudinaryStorage):

    def _get_resource_type(self, name: str) -> str:
        ext = os.path.splitext(name)[1].lower()
        return "raw" if ext in _RAW_EXTENSIONS else "image"

    def _upload(self, name, content):
        resource_type = self._get_resource_type(name)
        options = {
            "use_filename": True,
            "resource_type": resource_type,
            "tags": self.TAG,
        }
        folder = os.path.dirname(name)
        if folder:
            options["folder"] = folder
        if resource_type == "raw":
            # Make raw resources publicly accessible on the CDN, matching
            # the default behaviour of image resources.
            options["access_mode"] = "public"
        return cloudinary.uploader.upload(content, **options)

    def _open(self, name, mode="rb"):
        """
        Download a Cloudinary file via the authenticated Admin API endpoint.

        Uses private_download_url() which hits api.cloudinary.com with an
        HMAC signature (timestamp + api_key + api_secret).  This works for
        ALL resource types and access_mode settings — unlike a plain CDN GET
        which returns 401 for raw resources that lack access_mode='public'.
        """
        resource_type = self._get_resource_type(name)
        public_id = self._prepend_prefix(name)

        # Derive the format (extension without dot) for the API call.
        ext = os.path.splitext(name)[1].lstrip(".")  # e.g. "pdf", "jpg"

        download_url = cloudinary.utils.private_download_url(
            public_id,
            ext,
            resource_type=resource_type,
            type="upload",
        )

        resp = requests.get(download_url, timeout=30)
        if resp.status_code == 404:
            raise IOError(f"Cloudinary resource not found: {public_id}")
        resp.raise_for_status()

        file = ContentFile(resp.content)
        file.name = name
        file.mode = mode
        return file
