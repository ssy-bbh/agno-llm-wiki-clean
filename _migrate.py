import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("113.249.91.68", port=22, username="root", password="Cisdi@Abcd", timeout=15)

REMOTE = "/mnt/vdb/llm-wiki-os"
WIKI = f"{REMOTE}/data/wiki"

# First: identify which dirs at data/wiki/ root are user_id dirs vs old workspaces
# Known user_ids from the system
print("=== Identifying old workspaces vs user dirs ===")
_, stdout, _ = client.exec_command(f"""
cd {WIKI}
# Known user_ids from the auth database
KNOWN_USERS="sybh admin testuser1 testuser2 test123 testuser001 user_a"

echo "All directories at data/wiki/ root:"
ls -d */ 2>/dev/null

echo ""
echo "Old workspaces (not user_id dirs):"
for d in */; do
    d="${{d%/}}"
    IS_USER=0
    for u in $KNOWN_USERS; do
        if [ "$d" = "$u" ]; then
            IS_USER=1
            break
        fi
    done
    if [ "$IS_USER" = "0" ]; then
        CONCEPTS=$(find "$d/concepts" -name '*.md' 2>/dev/null | wc -l)
        INDEX=$(test -f "$d/index.md" && echo "yes" || echo "no")
        echo "  $d  (concepts: $CONCEPTS, index: $INDEX)"
    fi
done
""")
print(stdout.read().decode().strip())

# Migrate: move old workspaces into data/wiki/sybh/
print("\n=== Migrating old workspaces to sybh ===")
_, stdout, _ = client.exec_command(f"""
cd {WIKI}
KNOWN_USERS="sybh admin testuser1 testuser2 test123 testuser001 user_a"

mkdir -p sybh

for d in */; do
    d="${{d%/}}"
    IS_USER=0
    for u in $KNOWN_USERS; do
        if [ "$d" = "$u" ]; then
            IS_USER=1
            break
        fi
    done
    if [ "$IS_USER" = "0" ]; then
        # Skip if already exists in sybh
        if [ -d "sybh/$d" ]; then
            echo "  SKIP (already exists): $d -> sybh/$d"
        else
            mv "$d" "sybh/$d"
            echo "  MOVED: $d -> sybh/$d"
        fi
    fi
done

echo ""
echo "=== After migration ==="
echo "sybh workspaces:"
ls sybh/
""")
print(stdout.read().decode().strip())

# Also migrate data/raw/ the same way
print("\n=== Checking data/raw/ ===")
_, stdout, _ = client.exec_command(f"""
cd {REMOTE}/data/raw 2>/dev/null
if [ -d "." ]; then
    echo "Contents:"
    ls -la
    echo ""
    KNOWN_USERS="sybh admin testuser1 testuser2 test123 testuser001 user_a"
    mkdir -p sybh
    for d in */; do
        [ "$d" = "*/" ] && continue
        d="${{d%/}}"
        IS_USER=0
        for u in $KNOWN_USERS; do
            if [ "$d" = "$u" ]; then
                IS_USER=1
                break
            fi
        done
        if [ "$IS_USER" = "0" ]; then
            if [ -d "sybh/$d" ]; then
                echo "  SKIP: $d"
            else
                mv "$d" "sybh/$d"
                echo "  MOVED: $d -> sybh/$d"
            fi
        fi
    done
else
    echo "No data/raw/ directory"
fi
""")
print(stdout.read().decode().strip())

# Verify via API
print("\n=== Verify sybh workspaces via API ===")
_, stdout, _ = client.exec_command("""
TOKEN=$(curl -s -X POST http://localhost:8888/api/auth/login -H 'Content-Type: application/json' -d '{"username":"sybh","password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
curl -s "http://localhost:8888/api/workspaces" -H "Authorization: Bearer $TOKEN"
""")
print(f"\nWorkspaces: {stdout.read().decode().strip()}")

client.close()
