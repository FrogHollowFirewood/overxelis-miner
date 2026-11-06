#!/usr/bin/env python3
"""One-shot fixed beta.4 publication. Refuse existing state; never resume/delete."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request

REPO = 'FrogHollowFirewood/overxelis-miner'
BRANCH = 'refs/heads/release/beta4-public-preview2-20261106'
TARGET = 'd7ac5a593f0663b75f0cc08f6d3e18e0d42dc772'
TAG = 'v1.0.0-beta.4-public-preview.2'
TITLE = 'OverXelis Miner 1.0.0-beta.4 · Crash-fix public source preview 2'
MANIFEST_SHA = '3bcc699a8e7252584b2b0df15a0943b9299b35b4ba0c48e32982f9eb555f2b5e'
BODY_PATH = 'docs/releases/beta4-public-preview.2.md'
BODY_SHA = '0f73b96ee877bd4e7b06905eefc442be842e26096052bf5197a14d2e0364148a'
NEW_PATHS = {'.github/workflows/publish-beta4.yml',
             'tools/publish-beta4-release.py', BODY_PATH}
ARCHIVE = 'OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz'
ASSETS = (('docs/downloads/OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz', 314326, '4ede37b957b5024611f63714f4593bd60a849c0dd9c14594490353c56bdb53da', 'application/gzip'), ('docs/downloads/SHA256SUMS-beta.4-public-source-preview.2.txt', 126, 'dab25080746aa0957357105a429c9d995c1fb7fab4593f38f5ae9bf6c28e6768', 'text/plain'), ('docs/downloads/BETA4-HOTFIX-VALIDATION-NOTES.md', 7867, '4af7cde688f1633b21a8df0aa2f9ea958f0749449c1508f8531c1ff6b848325b', 'text/markdown'), ('docs/evidence/beta4-hotfix-validation-20261106.json', 13410, 'd2c65b1a7bbcc297ce0034e6f7fdc846303f6ebf70dfc55bfc62ecc1139841d4', 'application/json'))
API = 'https://api.github.com/repos/' + REPO
UPLOAD = 'https://uploads.github.com/repos/' + REPO


class Refusal(Exception):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Duplicate JSON key refused')
            result[key] = value
        return result
    def invalid_constant(_):
        raise Refusal('Nonfinite JSON refused')
    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def read_regular(root, name, limit=8 * 1024 * 1024):
    parts = PurePosixPath(name).parts
    need(parts and not name.startswith('/') and '..' not in parts and '\\' not in name,
         'Unsafe local path refused')
    path = root
    for part in parts[:-1]:
        path = path / part
        need(stat.S_ISDIR(path.lstat().st_mode), 'Non-directory local parent refused')
    fd = os.open(path / parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
             'Nonregular, linked or oversized local file refused')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(identity(before) == identity(after) and len(raw) == before.st_size,
             'Local file changed during read')
        return raw
    finally:
        os.close(fd)


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=15, check=False)
    need(result.returncode == 0, 'Read-only Git identity check failed')
    need(len(result.stdout) < 65536, 'Git identity response exceeds bound')
    return result.stdout


def verify_local(root, env):
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_EVENT_NAME') == 'push'
         and env.get('GITHUB_REPOSITORY') == REPO and env.get('GITHUB_REF') == BRANCH,
         'Wrong workflow repository, event or branch')
    head = env.get('GITHUB_SHA', '')
    need(re.fullmatch('[0-9a-f]{40}', head) and head != TARGET, 'Invalid workflow commit')
    need(git(root, 'rev-parse', 'HEAD').decode().strip() == head, 'Checkout is not GITHUB_SHA')
    parents = git(root, 'rev-list', '--parents', '-n', '1', head).decode().split()
    need(parents == [head, TARGET], 'Workflow commit must have exactly the fixed candidate parent')
    changed = git(root, 'diff-tree', '-z', '--no-commit-id', '--name-status',
                  '--no-renames', '--no-ext-diff', '-r', TARGET, head).split(b'\0')
    need(changed[-1] == b'' and len(changed) == 7,
         'Workflow commit must add exactly three paths')
    need({(changed[i].decode(), changed[i + 1].decode()) for i in range(0, 6, 2)}
         == {('A', p) for p in NEW_PATHS}, 'Unexpected workflow commit delta')
    body = read_regular(root, BODY_PATH)
    need(digest(body) == BODY_SHA, 'Release body differs from reviewed bytes')
    manifest_raw = read_regular(root, 'miner/SOURCE-MANIFEST.json')
    need(digest(manifest_raw) == MANIFEST_SHA, 'Wrong source manifest')
    files = strict_json(manifest_raw).get('files')
    need(type(files) is dict and len(files) == 69, 'Wrong tracked source inventory')
    for name, expected in files.items():
        need(type(name) is str and type(expected) is str
             and digest(read_regular(root, 'miner/' + name)) == expected,
             'Tracked source differs from manifest')
    actual = set()
    for base, dirs, names in os.walk(root / 'miner', followlinks=False,
                                     onerror=lambda _: (_ for _ in ()).throw(Refusal('Source walk failed'))):
        for name in dirs:
            need(stat.S_ISDIR((Path(base) / name).lstat().st_mode), 'Linked source directory refused')
        for name in names:
            p = Path(base) / name
            need(stat.S_ISREG(p.lstat().st_mode), 'Nonregular source inventory entry')
            actual.add(p.relative_to(root / 'miner').as_posix())
    need(actual == set(files) | {'SOURCE-MANIFEST.json'}, 'Source inventory is not exactly 70 files')
    assets = []
    for name, size, expected, content_type in ASSETS:
        raw = read_regular(root, name)
        need(len(raw) == size and digest(raw) == expected, 'Release asset size or digest differs')
        assets.append((Path(name).name, raw, expected, content_type))
    with tarfile.open(fileobj=io.BytesIO(assets[0][1]), mode='r:gz') as archive:
        seen = set()
        prefix = ARCHIVE.removesuffix('.tar.gz') + '/'
        for member in archive:
            need(member.isfile() and member.name.startswith(prefix), 'Nonregular archive member')
            name = member.name[len(prefix):]
            need(name not in seen and name in actual, 'Unexpected archive member')
            seen.add(name)
            expected = MANIFEST_SHA if name == 'SOURCE-MANIFEST.json' else files[name]
            need(digest(archive.extractfile(member).read()) == expected, 'Archive source hash differs')
        need(seen == actual, 'Archive is not the exact source inventory')
    return body.decode('utf-8'), assets


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class GitHub:
    def __init__(self, token):
        need(type(token) is str and 0 < len(token) <= 4096
             and '\r' not in token and '\n' not in token, 'Missing or invalid workflow token')
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, expected=200, payload=None, upload=None, content_type=None):
        # All URLs are constructed here; no server-supplied URL or redirect is followed.
        need(path.startswith('/') and not path.startswith('//'), 'Invalid API path')
        base = UPLOAD if upload is not None else API
        data = upload if upload is not None else (None if payload is None else
                json.dumps(payload, separators=(',', ':'), allow_nan=False).encode())
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                   'User-Agent': 'OverXelis-beta4-reviewed-publisher',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if data is not None:
            headers['Content-Type'] = content_type if upload is not None else 'application/json'
        request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                code = response.status
                raw = response.read(2 * 1024 * 1024 + 1)
            need(code == expected and len(raw) <= 2 * 1024 * 1024, 'Unexpected GitHub response')
            return strict_json(raw)
        except urllib.error.HTTPError as error:
            if error.code == 404 and expected == 404:
                return None
            raise Refusal('GitHub HTTP %d; stopped without automatic cleanup or retry' % error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise Refusal('GitHub transport failure; inspect partial state before any retry') from None


def positive_id(value):
    need(type(value) is int and value > 0, 'Invalid GitHub object ID')
    return value


def check_tag(value):
    need(type(value) is dict and value.get('ref') == 'refs/tags/' + TAG
         and value.get('object', {}).get('type') == 'commit'
         and value['object'].get('sha') == TARGET, 'Tag target verification failed')


def check_release(value, body, draft, release_id=None):
    need(type(value) is dict and value.get('tag_name') == TAG and value.get('name') == TITLE
         and value.get('target_commitish') == TARGET and value.get('body') == body
         and value.get('prerelease') is True and value.get('draft') is draft,
         'Release metadata verification failed')
    ident = positive_id(value.get('id'))
    need(release_id is None or release_id == ident, 'Release identity changed')
    return ident


def check_asset(value, asset):
    name, raw, expected, _ = asset
    need(type(value) is dict and value.get('name') == name and value.get('state') == 'uploaded'
         and type(value.get('size')) is int and value['size'] == len(raw)
         and value.get('digest') == 'sha256:' + expected, 'Uploaded asset verification failed')
    positive_id(value.get('id'))


def verify_assets(api, release_id, assets):
    listing = api.request('GET', '/releases/%d/assets?per_page=100&page=1' % release_id)
    need(type(listing) is list and len(listing) == len(assets), 'Release does not contain exactly four assets')
    by_name = {v.get('name'): v for v in listing if type(v) is dict}
    need(set(by_name) == {a[0] for a in assets}, 'Release asset names differ')
    for asset in assets:
        check_asset(by_name[asset[0]], asset)


def publish(api, body, assets):
    # Authenticated fixed-page traversal includes draft releases. 404 is accepted only
    # at the two exact absence probes, never as a substitute for a failed listing.
    for page in range(1, 21):
        listing = api.request('GET', '/releases?per_page=100&page=%d' % page)
        need(type(listing) is list and len(listing) <= 100, 'Malformed or unbounded release listing')
        need(all(type(r) is dict and type(r.get('tag_name')) is str for r in listing),
             'Malformed release listing entry')
        need(not any(r['tag_name'] == TAG for r in listing), 'Existing release or draft refused')
        if len(listing) < 100:
            break
    else:
        raise Refusal('Release pagination limit reached; absence not proved')
    api.request('GET', '/releases/tags/' + TAG, expected=404)
    api.request('GET', '/git/ref/tags/' + TAG, expected=404)
    commit = api.request('GET', '/commits/' + TARGET)
    need(type(commit) is dict and commit.get('sha') == TARGET, 'Fixed publication candidate unavailable')
    print('Preflight passed: fixed candidate and four local assets verified; tag/release absent.', flush=True)
    tag = api.request('POST', '/git/refs', expected=201,
                      payload={'ref': 'refs/tags/' + TAG, 'sha': TARGET})
    check_tag(tag)
    check_tag(api.request('GET', '/git/ref/tags/' + TAG))
    release = api.request('POST', '/releases', expected=201, payload={
        'tag_name': TAG, 'target_commitish': TARGET, 'name': TITLE, 'body': body,
        'draft': True, 'prerelease': True, 'generate_release_notes': False, 'make_latest': 'false'})
    ident = check_release(release, body, True)
    print('Created draft release ID %d; any failure leaves it for inspection.' % ident, flush=True)
    for asset in assets:
        name, raw, _, content_type = asset
        value = api.request('POST', '/releases/%d/assets?name=%s' %
                            (ident, urllib.parse.quote(name, safe='')), expected=201,
                            upload=raw, content_type=content_type)
        check_asset(value, asset)
    check_release(api.request('GET', '/releases/%d' % ident), body, True, ident)
    verify_assets(api, ident, assets)
    check_tag(api.request('GET', '/git/ref/tags/' + TAG))
    final = api.request('PATCH', '/releases/%d' % ident,
                        payload={'draft': False, 'prerelease': True, 'make_latest': 'false'})
    check_release(final, body, False, ident)
    check_release(api.request('GET', '/releases/%d' % ident), body, False, ident)
    verify_assets(api, ident, assets)
    check_tag(api.request('GET', '/git/ref/tags/' + TAG))
    print('Published and verified prerelease ID %d at fixed commit %s.' % (ident, TARGET), flush=True)
    return ident


OLD_BODY_SHA = '07a417a39e2ca3e2a3e397d3764f9cfe5b9a53df497abcef4e0d11bb60c84e36'
OLD_ASSETS = {'BETA4-PUBLIC-VALIDATION-NOTES.md': (7906, 'sha256:b1a3ad95839e8cfd408c615c78faa90f9fc22730e826776e2ce5a9c8f1ea6f3d'), 'beta4-validation-20261106.json': (9970, 'sha256:2ca8f35432562bcb51cce3c669703f1c37a17d543fc39162b7c3b7998ca06720'), 'OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz': (309121, 'sha256:7c0e9bf745d22c86bf186e360ed2a8cc23ec5bdb7e188adf4fd1c7a4a24c5cd4'), 'SHA256SUMS-beta.4-public-source-preview.1.txt': (126, 'sha256:95d435f5f5d017d5aeeaa85f5c206ce3931765ee63cb4ca76b57d94113bd3ee9')}
OLD_WARNING = '> **Superseded: use [beta.4 crash-fix source preview 2](https://github.com/FrogHollowFirewood/overxelis-miner/releases/tag/v1.0.0-beta.4-public-preview.2).** This original preview can stop on an integer division-by-zero fault. Its archives, checksums and historical measurements are preserved below; the old hour result does not qualify the hotfix.\n\n'

def mark_previous_superseded(api):
    path='/releases/tags/v1.0.0-beta.4-public-preview.1'
    previous=api.request('GET',path)
    need(previous.get('id') == 436807143 and previous.get('tag_name') == 'v1.0.0-beta.4-public-preview.1', 'Previous release identity changed')
    need(digest(previous.get('body','').encode()) == OLD_BODY_SHA, 'Previous release body changed; inspect before editing')
    def assets_of(value):
        return {a['name']:(a['size'],a.get('digest')) for a in value.get('assets',[])}
    need(assets_of(previous)==OLD_ASSETS,'Previous release assets changed')
    body=OLD_WARNING+previous['body']
    updated=api.request('PATCH','/releases/436807143',payload={'body':body})
    need(updated.get('body')==body and assets_of(updated)==OLD_ASSETS,'Superseded note or preserved assets mismatch')
    final=api.request('GET',path)
    need(final.get('body')==body and assets_of(final)==OLD_ASSETS,'Previous release verification failed')
    print('Marked preview 1 superseded; original body and all assets preserved.',flush=True)


def main():
    body, assets = verify_local(Path.cwd(), os.environ)
    api=GitHub(os.environ.get('GH_TOKEN'))
    result=publish(api, body, assets)
    mark_previous_superseded(api)
    return result


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        # No raw HTTP bodies, request objects, token, environment or private paths.
        message = str(error) if isinstance(error, Refusal) else 'Local validation or publication stopped'
        print('PUBLICATION STOPPED: ' + message + '. Partial state is retained for inspection.', file=sys.stderr)
        raise SystemExit(1)
