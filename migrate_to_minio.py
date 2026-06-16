from minio import Minio
from pathlib import Path

client = Minio("***",
               access_key="***", secret_key="***", secure=False)
BUCKET = "wiki-test"
count = 0
for f in Path("data").rglob("*"):
    if not f.is_file():
        continue
    if f.suffix in (".db",) or "lancedb" in str(f) or "__pycache__" in str(f):
        print(f"⏭️  跳过: {f.name}")
        continue
    key = str(f.relative_to(Path("data"))).replace("\\", "/")
    # 加 wiki/ 或 raw/ 前缀取决于路径本身
    # 因为 relative_to(data) 已经包含 wiki/ 或 raw/
    full_key = key
    client.fput_object(BUCKET, full_key, str(f))
    count += 1
    print(f"✅ {full_key}")
print(f"\n迁移完成，共上传 {count} 个文件")
