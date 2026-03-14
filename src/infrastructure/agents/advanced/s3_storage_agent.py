#!/usr/bin/env python3
"""
S3StorageAgent - Agent spécialisé dans la gestion du stockage S3/MinIO pour Tawiza-V2
Gestion intelligente des fichiers, buckets, synchronisation et analytics de stockage
"""

import hashlib
import io
import mimetypes
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

try:
    from minio import Minio
    from minio.commonconfig import Tags
    from minio.error import S3Error

    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    logger.warning("MinIO SDK not installed. Install with: pip install minio")


@dataclass
class S3Object:
    """Représentation d'un objet S3"""

    bucket: str
    key: str
    size: int
    last_modified: datetime
    etag: str
    content_type: str
    metadata: dict[str, str] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class BucketInfo:
    """Informations sur un bucket S3"""

    name: str
    creation_date: datetime
    object_count: int = 0
    total_size: int = 0
    versioning_enabled: bool = False


@dataclass
class UploadResult:
    """Résultat d'un upload"""

    success: bool
    bucket: str
    key: str
    etag: str | None = None
    version_id: str | None = None
    size: int = 0
    error: str | None = None
    url: str | None = None


@dataclass
class StorageAnalytics:
    """Analytics de stockage"""

    total_buckets: int
    total_objects: int
    total_size_bytes: int
    total_size_human: str
    objects_by_type: dict[str, int]
    size_by_bucket: dict[str, int]
    largest_objects: list[S3Object]
    oldest_objects: list[S3Object]
    recent_objects: list[S3Object]
    generated_at: str


class S3StorageAgent:
    """Agent spécialisé dans la gestion du stockage S3/MinIO"""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        secure: bool = False,
        region: str = "us-east-1",
    ):
        """Initialiser l'agent S3

        Args:
            endpoint: URL du serveur MinIO/S3 (ex: localhost:9002)
            access_key: Clé d'accès
            secret_key: Clé secrète
            secure: Utiliser HTTPS
            region: Région S3
        """
        self.name = "S3StorageAgent"
        self.agent_type = "storage"
        self.capabilities = [
            "bucket_management",
            "file_upload",
            "file_download",
            "file_sync",
            "storage_analytics",
            "lifecycle_management",
            "presigned_urls",
        ]

        # Configuration depuis variables d'environnement si non fournie
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9002")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "tawiza")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "")
        self.secure = secure
        self.region = region

        self.client: Minio | None = None
        self.is_connected = False

        # Cache pour éviter les requêtes répétitives
        self._bucket_cache: dict[str, BucketInfo] = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_time: dict[str, datetime] = {}

    async def connect(self) -> bool:
        """Établir la connexion avec le serveur S3"""
        if not MINIO_AVAILABLE:
            logger.error("MinIO SDK not available")
            return False

        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            # Test de connexion
            list(self.client.list_buckets())
            self.is_connected = True
            logger.info(f"🪣 Connected to S3 at {self.endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to S3: {e}")
            self.is_connected = False
            return False

    async def ensure_connected(self) -> bool:
        """S'assurer que la connexion est établie"""
        if not self.is_connected:
            return await self.connect()
        return True

    # ==================== BUCKET MANAGEMENT ====================

    async def list_buckets(self) -> list[BucketInfo]:
        """Lister tous les buckets"""
        if not await self.ensure_connected():
            return []

        try:
            buckets = self.client.list_buckets()
            result = []
            for bucket in buckets:
                info = BucketInfo(name=bucket.name, creation_date=bucket.creation_date)
                result.append(info)
            logger.info(f"Found {len(result)} buckets")
            return result
        except S3Error as e:
            logger.error(f"Error listing buckets: {e}")
            return []

    async def create_bucket(self, bucket_name: str) -> bool:
        """Créer un nouveau bucket"""
        if not await self.ensure_connected():
            return False

        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name, location=self.region)
                logger.info(f"🪣 Created bucket: {bucket_name}")
                return True
            logger.info(f"Bucket {bucket_name} already exists")
            return True
        except S3Error as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            return False

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """Supprimer un bucket (optionnellement vider d'abord)"""
        if not await self.ensure_connected():
            return False

        try:
            if force:
                # Supprimer tous les objets d'abord
                await self.delete_all_objects(bucket_name)

            self.client.remove_bucket(bucket_name)
            logger.info(f"🗑️ Deleted bucket: {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting bucket {bucket_name}: {e}")
            return False

    async def bucket_exists(self, bucket_name: str) -> bool:
        """Vérifier si un bucket existe"""
        if not await self.ensure_connected():
            return False
        return self.client.bucket_exists(bucket_name)

    # ==================== FILE OPERATIONS ====================

    async def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
        content_type: str = None,
        metadata: dict[str, str] = None,
    ) -> UploadResult:
        """Uploader un fichier vers S3"""
        if not await self.ensure_connected():
            return UploadResult(
                success=False, bucket=bucket_name, key=object_name, error="Not connected to S3"
            )

        try:
            # Créer le bucket si nécessaire
            await self.create_bucket(bucket_name)

            # Détecter le content-type si non fourni
            if not content_type:
                content_type, _ = mimetypes.guess_type(file_path)
                content_type = content_type or "application/octet-stream"

            # Upload
            result = self.client.fput_object(
                bucket_name, object_name, file_path, content_type=content_type, metadata=metadata
            )

            file_size = Path(file_path).stat().st_size
            url = f"http://{self.endpoint}/{bucket_name}/{object_name}"

            logger.info(
                f"📤 Uploaded {object_name} to {bucket_name} ({self._human_size(file_size)})"
            )

            return UploadResult(
                success=True,
                bucket=bucket_name,
                key=object_name,
                etag=result.etag,
                version_id=result.version_id,
                size=file_size,
                url=url,
            )
        except Exception as e:
            logger.error(f"Error uploading {file_path}: {e}")
            return UploadResult(success=False, bucket=bucket_name, key=object_name, error=str(e))

    async def upload_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] = None,
    ) -> UploadResult:
        """Uploader des bytes directement vers S3"""
        if not await self.ensure_connected():
            return UploadResult(
                success=False, bucket=bucket_name, key=object_name, error="Not connected to S3"
            )

        try:
            await self.create_bucket(bucket_name)

            data_stream = io.BytesIO(data)
            result = self.client.put_object(
                bucket_name,
                object_name,
                data_stream,
                length=len(data),
                content_type=content_type,
                metadata=metadata,
            )

            logger.info(f"📤 Uploaded {object_name} ({self._human_size(len(data))})")

            return UploadResult(
                success=True,
                bucket=bucket_name,
                key=object_name,
                etag=result.etag,
                version_id=result.version_id,
                size=len(data),
                url=f"http://{self.endpoint}/{bucket_name}/{object_name}",
            )
        except Exception as e:
            logger.error(f"Error uploading bytes: {e}")
            return UploadResult(success=False, bucket=bucket_name, key=object_name, error=str(e))

    async def download_file(
        self, bucket_name: str, object_name: str, destination_path: str
    ) -> bool:
        """Télécharger un fichier depuis S3"""
        if not await self.ensure_connected():
            return False

        try:
            self.client.fget_object(bucket_name, object_name, destination_path)
            logger.info(f"📥 Downloaded {object_name} to {destination_path}")
            return True
        except S3Error as e:
            logger.error(f"Error downloading {object_name}: {e}")
            return False

    async def download_bytes(self, bucket_name: str, object_name: str) -> bytes | None:
        """Télécharger un fichier en bytes"""
        if not await self.ensure_connected():
            return None

        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            logger.info(f"📥 Downloaded {object_name} ({self._human_size(len(data))})")
            return data
        except S3Error as e:
            logger.error(f"Error downloading {object_name}: {e}")
            return None

    async def delete_object(self, bucket_name: str, object_name: str) -> bool:
        """Supprimer un objet"""
        if not await self.ensure_connected():
            return False

        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"🗑️ Deleted {object_name} from {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting {object_name}: {e}")
            return False

    async def delete_all_objects(self, bucket_name: str) -> int:
        """Supprimer tous les objets d'un bucket"""
        if not await self.ensure_connected():
            return 0

        try:
            objects = self.client.list_objects(bucket_name, recursive=True)
            count = 0
            for obj in objects:
                self.client.remove_object(bucket_name, obj.object_name)
                count += 1
            logger.info(f"🗑️ Deleted {count} objects from {bucket_name}")
            return count
        except S3Error as e:
            logger.error(f"Error deleting objects from {bucket_name}: {e}")
            return 0

    # ==================== LISTING & SEARCH ====================

    async def list_objects(
        self, bucket_name: str, prefix: str = "", recursive: bool = True, max_keys: int = 1000
    ) -> list[S3Object]:
        """Lister les objets d'un bucket"""
        if not await self.ensure_connected():
            return []

        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=recursive)

            result = []
            for obj in objects:
                if len(result) >= max_keys:
                    break

                s3_obj = S3Object(
                    bucket=bucket_name,
                    key=obj.object_name,
                    size=obj.size or 0,
                    last_modified=obj.last_modified,
                    etag=obj.etag or "",
                    content_type=obj.content_type or "application/octet-stream",
                )
                result.append(s3_obj)

            logger.info(f"Found {len(result)} objects in {bucket_name}/{prefix}")
            return result
        except S3Error as e:
            logger.error(f"Error listing objects: {e}")
            return []

    async def search_objects(
        self, bucket_name: str, pattern: str, content_type: str = None
    ) -> list[S3Object]:
        """Rechercher des objets par pattern dans le nom"""
        import fnmatch

        objects = await self.list_objects(bucket_name, recursive=True)
        results = []

        for obj in objects:
            if fnmatch.fnmatch(obj.key, pattern):
                if content_type is None or obj.content_type == content_type:
                    results.append(obj)

        logger.info(f"Found {len(results)} objects matching '{pattern}'")
        return results

    # ==================== PRESIGNED URLs ====================

    async def get_presigned_url(
        self, bucket_name: str, object_name: str, expires: int = 3600
    ) -> str | None:
        """Générer une URL présignée pour téléchargement"""
        if not await self.ensure_connected():
            return None

        try:
            url = self.client.presigned_get_object(
                bucket_name, object_name, expires=timedelta(seconds=expires)
            )
            logger.info(f"🔗 Generated presigned URL for {object_name}")
            return url
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None

    async def get_upload_url(
        self, bucket_name: str, object_name: str, expires: int = 3600
    ) -> str | None:
        """Générer une URL présignée pour upload"""
        if not await self.ensure_connected():
            return None

        try:
            await self.create_bucket(bucket_name)
            url = self.client.presigned_put_object(
                bucket_name, object_name, expires=timedelta(seconds=expires)
            )
            logger.info(f"🔗 Generated presigned upload URL for {object_name}")
            return url
        except S3Error as e:
            logger.error(f"Error generating upload URL: {e}")
            return None

    # ==================== SYNC OPERATIONS ====================

    async def sync_directory(
        self, local_dir: str, bucket_name: str, prefix: str = "", delete: bool = False
    ) -> dict[str, Any]:
        """Synchroniser un répertoire local avec S3"""
        if not await self.ensure_connected():
            return {"success": False, "error": "Not connected"}

        local_path = Path(local_dir)
        if not local_path.exists():
            return {"success": False, "error": f"Directory {local_dir} does not exist"}

        await self.create_bucket(bucket_name)

        stats = {"uploaded": 0, "skipped": 0, "deleted": 0, "errors": []}

        # Collecter les fichiers locaux
        local_files = {}
        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(local_path)
                object_key = f"{prefix}/{rel_path}" if prefix else str(rel_path)
                object_key = object_key.replace("\\", "/")
                local_files[object_key] = file_path

        # Collecter les objets S3 existants
        remote_objects = await self.list_objects(bucket_name, prefix=prefix)
        remote_keys = {obj.key for obj in remote_objects}

        # Upload des fichiers nouveaux/modifiés
        for object_key, file_path in local_files.items():
            try:
                # Calculer le hash pour détecter les changements
                file_hash = self._file_md5(file_path)

                # Vérifier si le fichier existe et est identique
                if object_key in remote_keys:
                    remote_obj = next((o for o in remote_objects if o.key == object_key), None)
                    if remote_obj and remote_obj.etag.strip('"') == file_hash:
                        stats["skipped"] += 1
                        continue

                result = await self.upload_file(bucket_name, object_key, str(file_path))
                if result.success:
                    stats["uploaded"] += 1
                else:
                    stats["errors"].append(f"Failed to upload {object_key}")
            except Exception as e:
                stats["errors"].append(f"Error with {object_key}: {e}")

        # Supprimer les fichiers distants non présents localement
        if delete:
            for remote_key in remote_keys:
                if remote_key not in local_files:
                    if await self.delete_object(bucket_name, remote_key):
                        stats["deleted"] += 1

        logger.info(
            f"📁 Sync complete: {stats['uploaded']} uploaded, {stats['skipped']} skipped, {stats['deleted']} deleted"
        )
        return {"success": True, **stats}

    # ==================== ANALYTICS ====================

    async def get_storage_analytics(self) -> StorageAnalytics:
        """Obtenir des analytics sur le stockage"""
        if not await self.ensure_connected():
            return None

        buckets = await self.list_buckets()

        total_objects = 0
        total_size = 0
        objects_by_type: dict[str, int] = {}
        size_by_bucket: dict[str, int] = {}
        all_objects: list[S3Object] = []

        for bucket in buckets:
            objects = await self.list_objects(bucket.name)
            bucket_size = 0

            for obj in objects:
                total_objects += 1
                total_size += obj.size
                bucket_size += obj.size
                all_objects.append(obj)

                # Stats par type de contenu
                content_type = obj.content_type.split("/")[0]
                objects_by_type[content_type] = objects_by_type.get(content_type, 0) + 1

            size_by_bucket[bucket.name] = bucket_size

        # Trier pour obtenir les plus gros/anciens/récents
        all_objects.sort(key=lambda x: x.size, reverse=True)
        largest = all_objects[:10]

        all_objects.sort(key=lambda x: x.last_modified)
        oldest = all_objects[:10]

        all_objects.sort(key=lambda x: x.last_modified, reverse=True)
        recent = all_objects[:10]

        return StorageAnalytics(
            total_buckets=len(buckets),
            total_objects=total_objects,
            total_size_bytes=total_size,
            total_size_human=self._human_size(total_size),
            objects_by_type=objects_by_type,
            size_by_bucket=size_by_bucket,
            largest_objects=largest,
            oldest_objects=oldest,
            recent_objects=recent,
            generated_at=datetime.utcnow().isoformat(),
        )

    # ==================== UTILITY METHODS ====================

    def _human_size(self, size_bytes: int) -> str:
        """Convertir les bytes en format lisible"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def _file_md5(self, file_path: Path) -> str:
        """Calculer le MD5 d'un fichier"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def health_check(self) -> dict[str, Any]:
        """Vérifier l'état de santé de la connexion S3"""
        connected = await self.ensure_connected()

        if not connected:
            return {"status": "unhealthy", "connected": False, "endpoint": self.endpoint}

        try:
            buckets = list(self.client.list_buckets())
            return {
                "status": "healthy",
                "connected": True,
                "endpoint": self.endpoint,
                "bucket_count": len(buckets),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "endpoint": self.endpoint,
                "error": str(e),
            }

    async def close(self):
        """Fermer la connexion"""
        self.client = None
        self.is_connected = False
        logger.info("🪣 S3 connection closed")


# Singleton instance
_s3_agent: S3StorageAgent | None = None


def get_s3_agent() -> S3StorageAgent:
    """Obtenir l'instance singleton de l'agent S3"""
    global _s3_agent
    if _s3_agent is None:
        _s3_agent = S3StorageAgent()
    return _s3_agent
