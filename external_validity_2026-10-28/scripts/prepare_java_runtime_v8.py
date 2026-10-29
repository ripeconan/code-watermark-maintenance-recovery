"""Prime the dynamic runtime artifact identified in original-only Java logs."""
import datetime,json,tempfile
from pathlib import Path
import test_temporal as base
ROOT=base.ROOT
ARTIFACTS=['org.junit.vintage:junit-vintage-engine:6.1.3']

def main():
    dest=ROOT/'records/java_v8_runtime_warmups.json'
    if dest.exists():
        saved=json.loads(dest.read_text());assert saved['artifacts']==ARTIFACTS and saved['ready'];return
    records=[]
    for artifact in ARTIFACTS:
        with tempfile.TemporaryDirectory(prefix='runtime-v8-',dir=ROOT/'work') as td:
            work=Path(td)
            (work/'pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>research.environment</groupId><artifactId>runtime-cache</artifactId><version>1</version></project>')
            command=base.maven('apache/commons-csv')+['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get','-Dartifact='+artifact,'-Dtransitive=true']
            log=ROOT/'logs'/('java_v8_runtime_'+base.sha(artifact.encode())[:24]+'.log')
            result=base.run_limited(base.sandbox(work,'checkstyle/checkstyle',network=True)+command,work,log,timeout=300)
            records.append(dict(result,artifact=artifact,command=command,log=str(log.relative_to(ROOT))))
    saved=dict(artifacts=ARTIFACTS,ready=all(r['status']=='ok' for r in records),records=records,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    dest.write_text(json.dumps(saved,indent=2));print(json.dumps(saved,indent=2),flush=True)
    assert saved['ready'],'runtime priming failed; retain log and diagnose'

if __name__=='__main__':main()
