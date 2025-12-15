import asyncio
import json
import requests
from streamget import ShopeeLiveStream

def resolve_url(u: str) -> str:
    try:
        r = requests.get(u, allow_redirects=True, timeout=15)
        return r.url
    except Exception:
        return u

short_url = "https://id.shp.ee/sGQ6esn"
final_url = resolve_url(short_url)
live = ShopeeLiveStream()

raw = asyncio.run(live.fetch_web_stream_data(final_url, process_data=False))
print("Resolved URL:", final_url)
print("Raw preview:", (raw or "")[:200])

try:
    data = json.loads(raw)
except Exception as e:
    raise SystemExit(f"Failed to parse stream data: {e}")

stream_obj = asyncio.run(live.fetch_stream_url(data, "OD"))
json_str = stream_obj.to_json()