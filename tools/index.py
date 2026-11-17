import os
import sqlite3
import json
import re
import sys

DB_PATH = "build/site.db"
CONTENT_DIR = "content"
SEARCH_JSON = "static/search.json"
TAGS_JSON = "data/tags.json"

def parse_front_matter(filepath, include_drafts=False):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        return None
    
    fm_raw, body = match.groups()
    meta = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                tags = [t.strip().strip("'\"") for t in val[1:-1].split(",")]
                meta[key] = tags
            elif val.lower() == "true":
                meta[key] = True
            elif val.lower() == "false":
                meta[key] = False
            else:
                meta[key] = val.strip("'\"")
                
    if meta.get("draft", False) and not include_drafts:
        return None
        
    return meta, body

def init_db(conn):
    conn.execute("DROP TABLE IF EXISTS posts;")
    conn.execute("""
        CREATE TABLE posts (
            url TEXT PRIMARY KEY,
            title TEXT,
            date TEXT,
            tags TEXT,
            body TEXT
        );
    """)
    conn.commit()

def index_posts(conn, include_drafts=False):
    init_db(conn)
    count = 0
    for root, _, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                res = parse_front_matter(filepath, include_drafts)
                if not res:
                    continue
                meta, body = res
                
                rel_path = os.path.relpath(filepath, CONTENT_DIR)
                url = "/" + rel_path.replace(".md", "/").replace("_index/", "")
                title = meta.get("title", "Sin título")
                date = meta.get("date", "")
                tags = json.dumps(meta.get("tags", []))
                
                conn.execute(
                    "INSERT OR REPLACE INTO posts (url, title, date, tags, body) VALUES (?, ?, ?, ?, ?);",
                    (url, title, date, tags, body)
                )
                count += 1
    conn.commit()
    return count

def generate_json(conn):
    os.makedirs("build", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # Q_SEARCH
    cursor = conn.execute("SELECT url, title, body, tags FROM posts;")
    rows = cursor.fetchall()
    search_data = []
    for r in rows:
        search_data.append({
            "url": r[0],
            "title": r[1],
            "body": r[2],
            "tags": json.loads(r[3])
        })
    with open(SEARCH_JSON, "w", encoding="utf-8") as f:
        json.dump(search_data, f, ensure_ascii=False, indent=2)
        
    # Q_TAGS
    cursor = conn.execute("""
        SELECT value AS tag, COUNT(*) as total 
        FROM posts, json_each(posts.tags) 
        GROUP BY tag 
        ORDER BY total DESC;
    """)
    tags_data = [{"tag": r[0], "total": r[1]} for r in cursor.fetchall()]
    with open(TAGS_JSON, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    include_drafts = "--drafts" in sys.argv
    os.makedirs("build", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    count = index_posts(conn, include_drafts)
    generate_json(conn)
    print(f"index: {count} páginas (drafts={include_drafts}) → static/search.json, data/tags.json")
    conn.close()
