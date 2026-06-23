"""
core/storage.py - MinIO storage (server-side only)
"""
import os, io, logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _get_wiki_base():
    return PROJECT_ROOT / "data" / "wiki"

class MinIOStorage:
    def __init__(self, endpoint, access_key, secret_key, bucket="llm-wiki", secure=False):
        from minio import Minio
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket
        self.enabled = True
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
    def list_user_workspaces(self, user_id):
        if not self.enabled: return []
        prefix = user_id + "/"
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=False)
        result = []
        for obj in objects:
            name = obj.object_name.rstrip("/")
            ws = name[len(prefix):]
            if ws and ws != "raw":
                result.append(ws)
        result.sort()
        return result
    def ensure_workspace(self, user_id, workspace):
        if not self.enabled: return
        key = user_id + "/" + workspace + "/.workspace"
        if not self.exists(key):
            self.put(key, "created_by=" + user_id)
    def put(self, key, content, content_type="text/markdown"):
        data = content.encode("utf-8")
        self.client.put_object(self.bucket, key, io.BytesIO(data), len(data), content_type=content_type)
    def put_binary(self, key, data, content_type="application/octet-stream"):
        self.client.put_object(self.bucket, key, io.BytesIO(data), len(data), content_type=content_type)
    def get(self, key):
        try:
            resp = self.client.get_object(self.bucket, key)
            content = resp.read().decode("utf-8")
            resp.close(); resp.release_conn()
            return content
        except Exception: return None
    def exists(self, key):
        try:
            self.client.stat_object(self.bucket, key); return True
        except Exception: return False
    def list_objects(self, prefix):
        return [o.object_name for o in self.client.list_objects(self.bucket, prefix=prefix, recursive=True)]
    def delete(self, key):
        self.client.remove_object(self.bucket, key)
    def delete_file(self, user_id, workspace, rel_path):
        if not self.enabled: return
        key = user_id + "/" + workspace + "/" + rel_path.replace("\\", "/")
        try: self.delete(key)
        except: pass
    def sync_down(self, user_id, workspace):
        if not self.enabled: return
        prefix = user_id + "/" + workspace + "/"
        local_dir = _get_wiki_base() / user_id / workspace
        keys = self.list_objects(prefix)
        if not keys: return
        n = 0
        for key in keys:
            rel = key[len(prefix):]
            if not rel or rel == ".workspace": continue
            lp = local_dir / rel
            lp.parent.mkdir(parents=True, exist_ok=True)
            c = self.get(key)
            if c is not None:
                lp.write_text(c, encoding="utf-8"); n += 1
        if n: logger.info(f"sync_down: {user_id}/{workspace} -> {n}")
    def sync_up(self, user_id, workspace):
        if not self.enabled: return
        local_dir = _get_wiki_base() / user_id / workspace
        if not local_dir.exists(): return
        n = 0
        prefix = user_id + "/" + workspace + "/"
        for p in local_dir.rglob("*"):
            if not p.is_file(): continue
            if any(x.startswith(".") for x in p.parts): continue
            if p.suffix in (".tmp",".lock",".bak"): continue
            rel = str(p.relative_to(local_dir)).replace("\\","/")
            self.put(prefix + rel, p.read_text(encoding="utf-8")); n += 1
        if n: logger.info(f"sync_up: {user_id}/{workspace} -> {n}")
    def sync_up_file(self, user_id, workspace, rel_path):
        if not self.enabled: return
        lp = _get_wiki_base() / user_id / workspace / rel_path
        if not lp.exists(): return
        key = user_id + "/" + workspace + "/" + rel_path.replace("\\","/")
        self.put(key, lp.read_text(encoding="utf-8"))
    def put_raw_file(self, user_id, workspace, filename, data):
        if not self.enabled: return
        key = "raw/" + user_id + "/" + workspace + "/" + filename
        self.put_binary(key, data)
    def sync_up_raw(self, user_id, workspace):
        if not self.enabled: return
        ld = PROJECT_ROOT / "data" / "raw" / user_id / workspace
        if not ld.exists(): return
        n = 0
        prefix = "raw/" + user_id + "/" + workspace + "/"
        for p in ld.rglob("*"):
            if not p.is_file(): continue
            if any(x.startswith(".") for x in p.parts): continue
            rel = str(p.relative_to(ld)).replace("\\","/")
            self.put_binary(prefix + rel, p.read_bytes()); n += 1
        if n: logger.info(f"sync_up_raw: {user_id}/{workspace} -> {n}")
    def delete_workspace(self, user_id, workspace):
        if not self.enabled: return
        for pfx in [user_id+"/"+workspace+"/", "raw/"+user_id+"/"+workspace+"/"]:
            for k in self.list_objects(pfx): self.delete(k)

class LocalOnlyStorage:
    enabled = False
    def list_user_workspaces(self, u): return []
    def ensure_workspace(self, u, w): pass
    def sync_down(self, u, w): pass
    def sync_up(self, u, w): pass
    def sync_up_file(self, u, w, r): pass
    def put_raw_file(self, u, w, f, d): pass
    def sync_up_raw(self, u, w): pass
    def delete_workspace(self, u, w): pass
    def delete_file(self, u, w, r): pass
    def put(self, k, c, t="text/markdown"): pass
    def get(self, k): return None
    def exists(self, k): return False

_inst = None
def get_storage():
    global _inst
    if _inst is not None: return _inst
    ep = os.getenv("MINIO_ENDPOINT","").strip()
    ak = os.getenv("MINIO_ACCESS_KEY","").strip()
    sk = os.getenv("MINIO_SECRET_KEY","").strip()
    bk = os.getenv("MINIO_BUCKET","llm-wiki").strip()
    sec = os.getenv("MINIO_SECURE","false").lower() in ("true","1","yes")
    if ep and ak and sk:
        try:
            _inst = MinIOStorage(endpoint=ep, access_key=ak, secret_key=sk, bucket=bk, secure=sec)
            logger.info(f"MinIO enabled: {ep}")
        except Exception as e:
            logger.warning(f"MinIO failed: {e}"); _inst = LocalOnlyStorage()
    else:
        _inst = LocalOnlyStorage()
    return _inst
