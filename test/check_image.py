"""Inspect every image layer and boot a PDS against disposable storage."""
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request


image = sys.argv[1]
version = json.loads(Path('service/package.json').read_text())['dependencies']['@atproto/pds']
_, minor, patch = version.split('.')
expected_version = f'0.4.{minor}{int(patch):03d}'
with tempfile.TemporaryFile() as saved:
    subprocess.run(['docker', 'image', 'save', image], stdout=saved, check=True)
    saved.seek(0)
    with tarfile.open(fileobj=saved) as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
        for layer in manifest[0]['Layers']:
            with tarfile.open(fileobj=archive.extractfile(layer), mode='r|*') as contents:
                for member in contents:
                    parts = PurePosixPath(member.name).parts
                    assert '.git' not in parts, 'Git metadata found in an image layer'
                    if parts and parts[0] == 'app' and 'node_modules' not in parts:
                        assert not any(part in {'.github', '.devcontainer'} for part in parts), 'Checkout files found in an application layer'
                        assert not member.name.endswith('.env'), 'Environment file found in an application layer'
                    assert member.name.lstrip('./') not in {'pds.env', 'config/pds.env'}, 'Runtime credentials found in an image layer'
print('Every image layer excludes Git metadata and application environment files.')

# These are disposable CI values, never production credentials. No persistent
# host directories are mounted, and startup must not request a relay crawl.
container = subprocess.check_output([
    'docker', 'run', '--detach', '--rm', '-p', '127.0.0.1::3000',
    '--tmpfs', '/pds:rw,size=256m',
    '-e', 'PDS_HOSTNAME=pds-ci.invalid',
    '-e', 'PDS_DATA_DIRECTORY=/pds',
    '-e', 'PDS_BLOBSTORE_DISK_LOCATION=/pds/blobs',
    '-e', 'PDS_JWT_SECRET=' + '1' * 64,
    '-e', 'PDS_ADMIN_PASSWORD=disposable-ci-password',
    '-e', 'PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX=' + '2' * 64,
    '-e', 'PDS_RATE_LIMITS_ENABLED=true',
    '-e', 'PDS_INVITE_REQUIRED=true',
    '-e', 'PDS_CRAWLERS=', image], text=True).strip()
try:
    address = subprocess.check_output(['docker', 'port', container, '3000/tcp'], text=True).strip()
    base = 'http://' + address
    for _ in range(120):
        try:
            with urllib.request.urlopen(base + '/xrpc/_health', timeout=2) as response:
                assert response.status == 200
                assert json.load(response)['version'] == expected_version
            break
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    else:
        raise AssertionError('PDS did not become ready')
    with urllib.request.urlopen(base + '/xrpc/com.atproto.server.describeServer', timeout=5) as response:
        assert response.status == 200
        assert int(response.headers['RateLimit-Limit']) > 0
        assert json.load(response)['inviteCodeRequired'] is True
    subprocess.run(['docker', 'exec', container, 'sh', '-ec',
                    'for cmd in pds-account pds-create-invite-code pds-request-crawl pds-help goat; do command -v "$cmd" >/dev/null; done'], check=True)
    print(f'PDS {expected_version} starts with rate limits, invite gating, and admin commands.')
finally:
    subprocess.run(['docker', 'stop', container], check=True, stdout=subprocess.DEVNULL)
