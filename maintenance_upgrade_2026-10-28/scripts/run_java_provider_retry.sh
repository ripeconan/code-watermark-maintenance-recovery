set -eu
cd /home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028
export JAVA_HOME=/home2/icdm/crosslingual-codewatermark/publication_revision_20261028/tools/jdk-17.0.21+9
export MAVEN_OPTS='-Xmx1536m -XX:ActiveProcessorCount=1 -Djava.net.preferIPv4Stack=true'
timeout 500 tools/apache-maven-3.9.11/bin/mvn -B -f work/maven-provider/pom.xml -Dmaven.repo.local=/home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028/tools/m2 -Daether.connector.http.requestTimeout=30000 org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get -Dartifact=org.apache.maven.surefire:surefire-junit-platform:3.5.6
/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python -u scripts/test_project_local.py --language java --run-id javaprovider --limit 4
