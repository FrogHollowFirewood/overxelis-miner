import os,json,urllib.request,hashlib,subprocess
REPO='FrogHollowFirewood/overxelis-miner'
TARGET='2352a3a441dc50393ea9a21d8290e002cc81d986'
assert os.environ['GITHUB_REPOSITORY']==REPO
assert os.environ['GITHUB_REF']=='refs/heads/release/beta4-hour-report-20261106'
assert subprocess.check_output(['git','rev-parse','HEAD^'],text=True).strip()==TARGET
assert subprocess.check_output(['git','diff-tree','--no-commit-id','--name-status','-r','HEAD'],text=True).splitlines()==['A\t.github/workflows/publish-hour-addendum.yml','A\ttools/publish-hour-addendum.py']
def api(path,method='GET',payload=None):
 body=json.dumps(payload).encode() if payload is not None else None
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+path,data=body,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
def inventory(d):
 return sorted([{'name':a['name'],'size':a['size'],'digest':a['digest']} for a in d['assets']],key=lambda x:x['name'])
expected=json.loads("[{\"name\":\"beta4-hotfix-validation-20261106.json\",\"size\":13410,\"digest\":\"sha256:d2c65b1a7bbcc297ce0034e6f7fdc846303f6ebf70dfc55bfc62ecc1139841d4\"},{\"name\":\"BETA4-HOTFIX-VALIDATION-NOTES.md\",\"size\":7867,\"digest\":\"sha256:4af7cde688f1633b21a8df0aa2f9ea958f0749449c1508f8531c1ff6b848325b\"},{\"name\":\"OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz\",\"size\":314326,\"digest\":\"sha256:4ede37b957b5024611f63714f4593bd60a849c0dd9c14594490353c56bdb53da\"},{\"name\":\"SHA256SUMS-beta.4-public-source-preview.2.txt\",\"size\":126,\"digest\":\"sha256:dab25080746aa0957357105a429c9d995c1fb7fab4593f38f5ae9bf6c28e6768\"}]")
expected=sorted(expected,key=lambda x:x['name'])
assert api('/git/ref/heads/main')['object']['sha']==TARGET
d=api('/releases/436926746')
assert d['tag_name']=='v1.0.0-beta.4-public-preview.2' and d['target_commitish']=='d7ac5a593f0663b75f0cc08f6d3e18e0d42dc772'
assert not d['draft'] and d['prerelease'] and inventory(d)==expected
assert hashlib.sha256(d['body'].encode()).hexdigest()=='0f73b96ee877bd4e7b06905eefc442be842e26096052bf5197a14d2e0364148a', 'Release body changed; inspect before retrying'
addition="## Later validation addendum — 6 November 2026\n\nThe development hotfix has a completed logged hour: **60 minutes 27.49 seconds after warmup**, **119.739756 kH/s mean of 361 rounded local displays**, sampled minimum **119.517 kH/s**, and **444 accepted USER shares** in that interval (450 in the full session). Rejected and unresolved displays stayed at zero, and native workers closed normally after a requested stop.\n\nIts native library is byte-identical to the qualified preview-2 library; the development launcher retained its preview-1 banner. This is logged continuity evidence, not an exact raw-counter hour or an exact-edition launcher run. GPU activity, cooling, temperatures and native drop/undefined-skip diagnostics were not recorded for this session. No full fee cycle, long soak or 120 kH/s guarantee is established.\n\nRead the [dated hour report](https://froghollowfirewood.github.io/overxelis-miner/hotfix-hour.html) and [sanitized interval data](https://froghollowfirewood.github.io/overxelis-miner/evidence/beta4-hotfix-hour-continuity-20261106.json). All existing release assets, checksums and tags are unchanged. This addendum updates the measurement status; the original release-time notes below are preserved.\n\n---\n\n"
new=addition+d['body']
api('/releases/436926746','PATCH',{'body':new})
after=api('/releases/436926746')
assert after['body']==new and inventory(after)==expected
assert after['tag_name']==d['tag_name'] and after['target_commitish']==d['target_commitish']
print('Verified hour addendum; original release body and all four assets preserved.')
