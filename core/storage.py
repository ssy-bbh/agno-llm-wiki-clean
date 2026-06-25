"""core/storage.py — MinIO 对象存储封装"""
import io
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # 确保 .env 已加载（即使本模块先于 path_resolver 被导入）
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv 未安装，依赖系统环境变量或 IDE 注入

from minio import Minio
from minio.error import S3Error

BUCKET = os.environ.get("MINIO_BUCKET", "wiki-test")

def get_client() -> Minio:
    return Minio(
        endpoint=os.environ.get("MINIO_ENDPOINT", "***"),
        access_key=os.environ.get("MINIO_ACCESS_KEY", ""),
        secret_key=os.environ.get("MINIO_SECRET_KEY", ""),
        secure=False,
    )

def read(key: str) -> str:
    resp = get_client().get_object(BUCKET, key)
    try:
        return resp.read().decode("utf-8")
    finally:
        resp.close()
        resp.release_conn()

def write(key: str, content: str):
    data = content.encode("utf-8")
    get_client().put_object(BUCKET, key, io.BytesIO(data),
                            length=len(data), content_type="text/markdown")

def upload_file(key: str, local_path: str):
    """将本地文件上传到 MinIO"""
    get_client().fput_object(BUCKET, key, local_path)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """将字节数据上传到 MinIO（用于接收前端上传的文件流）"""
    get_client().put_object(BUCKET, key, io.BytesIO(data),
                            length=len(data), content_type=content_type)


def download_file(key: str, local_path: str):
    """从 MinIO 下载文件到本地路径（摄入时临时使用，用完即删）"""
    get_client().fget_object(BUCKET, key, local_path)

def exists(key: str) -> bool:
    try:
        get_client().stat_object(BUCKET, key)
        return True
    except S3Error:
        return False

def list_keys(prefix: str) -> list:
    return [obj.object_name for obj in
            get_client().list_objects(BUCKET, prefix=prefix, recursive=True)]

def delete(key: str):
    get_client().remove_object(BUCKET, key)


def delete_prefix(prefix: str) -> int:
    """删除指定前缀下的所有对象，返回删除数量"""
    from minio.deleteobjects import DeleteObject
    keys = list_keys(prefix)
    if not keys:
        return 0
    errors = list(get_client().remove_objects(
        BUCKET,
        [DeleteObject(key) for key in keys]
    ))
    if errors:
        print(f"⚠️ MinIO 批量删除 {prefix} 有 {len(errors)} 个对象删除失败", flush=True)
    return len(keys) - len(errors)


# ═══════════════════════════════════════════
# MinIO ↔ 本地同步（forge/inbox/radar 用）
# ═══════════════════════════════════════════

def sync_minio_to_local(prefix: str, local_dir: "Path") -> int:
    """将 MinIO 前缀下所有文件下载到本地目录，返回下载数量"""
    keys = list_keys(prefix)
    if not keys:
        return 0
    client = get_client()
    count = 0
    for key in keys:
        # 计算相对路径: wiki/user/ws/concepts/foo.md → concepts/foo.md
        rel = key[len(prefix):].lstrip("/")
        if not rel:
            continue
        target = local_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            client.fget_object(BUCKET, key, str(target))
            count += 1
        except Exception as e:
            print(f"  ⚠️ MinIO→Local 下载失败 {key}: {e}", flush=True)
    return count


def sync_local_to_minio(local_dir: "Path", prefix: str) -> int:
    """将本地目录下所有 .md 文件上传到 MinIO 前缀，返回上传数量"""
    if not local_dir.exists():
        return 0
    client = get_client()
    count = 0
    for f in local_dir.rglob("*.md"):
        rel = f.relative_to(local_dir).as_posix()
        key = f"{prefix}/{rel}"
        try:
            client.fput_object(BUCKET, key, str(f))
            count += 1
        except Exception as e:
            print(f"  ⚠️ Local→MinIO 上传失败 {key}: {e}", flush=True)
    return count
