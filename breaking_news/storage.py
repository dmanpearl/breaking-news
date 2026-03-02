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

This backend fixes both issues:

  _get_resource_type()  — returns 'raw' for PDFs, 'image' for everything else.
                          Used for upload, URL generation, and deletion.

  _upload()             — adds access_mode='public' for raw resources so the
                          file is publicly accessible without authentication.
                          Without this, Cloudinary raw uploads default to
                          authenticated delivery, returning 401 on plain GETs.

  _open()               — uses a short-lived signed download URL (via the
                          Cloudinary API) instead of a plain unauthenticated
                          GET. This is the fallback read path used by
                          field.read() in services.py and by exists()/size().
                          It works regardless of the resource's access_mode.
"""

import os

import cloudinary
import cloudinary.utils
import requests
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.core.files.base import ContentFile

# File extensions that must be stored as Cloudinary 'raw' resources.
# Everything else uses the default 'image' resource type.
_RAW_EXTENSIONS = {".pdf"}

# How long (seconds) a signed download URL stays valid.
# 60 s is more than enough — we fetch the bytes immediately.
_SIGNED_URL_TTL = 60


class SmartMediaCloudinaryStorage(MediaCloudinaryStorage):
    """
    MediaCloudinaryStorage that:
      * routes PDFs to resource_type='raw' (images stay as 'image')
      * uploads raw resources with access_mode='public' so they are
        fetchable without auth credentials
      * reads files back via a short-lived signed URL so field.read()
        always works, even for resources uploaded before this fix
    """

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
        # Raw resources default to authenticated delivery in Cloudinary.
        # Explicitly set access_mode='public' so they can be fetched without
        # API credentials — matching the behaviour of image resources.
        if resource_type == "raw":
            options["access_mode"] = "public"
        return cloudinary.uploader.upload(content, **options)

    def _open(self, name, mode="rb"):
        """
        Read a file back from Cloudinary using a short-lived signed URL.

        The base class does a plain unauthenticated requests.get(url), which
        returns 401 for raw resources that were uploaded without access_mode=
        'public' (i.e. files uploaded before this storage class was deployed).
        A signed URL works unconditionally regardless of access_mode.
        """
        resource_type = self._get_resource_type(name)
        public_id = self._prepend_prefix(name)

        # Build a short-lived signed URL using the Cloudinary Python SDK.
        signed_url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type=resource_type,
            type="upload",
            sign_url=True,
            expires_at=int(cloudinary.utils.now()) + _SIGNED_URL_TTL,
        )

        resp = requests.get(signed_url, timeout=30)
        if resp.status_code == 404:
            raise IOError(f"Cloudinary resource not found: {public_id}")
        resp.raise_for_status()

        file = ContentFile(resp.content)
        file.name = name
        file.mode = mode
        return file
