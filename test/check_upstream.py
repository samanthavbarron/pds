"""Report upstream version drift without changing dependencies or deploying."""
import json
from pathlib import Path
import urllib.request

local = json.loads(Path('service/package.json').read_text())['dependencies']['@atproto/pds']
url = 'https://raw.githubusercontent.com/bluesky-social/pds/main/service/package.json'
with urllib.request.urlopen(url, timeout=30) as response:
    upstream = json.load(response)['dependencies']['@atproto/pds']
print(f'Bundled @atproto/pds: {local}; upstream: {upstream}')
if local != upstream:
    raise SystemExit('Upstream PDS changed. Review and rebuild this fork, then deploy a reviewed digest with a backup.')
