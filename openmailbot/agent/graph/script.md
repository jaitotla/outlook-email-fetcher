# 1. Install Java (required for Neo4j)
sudo apt update
sudo apt install openjdk-17-jre-headless -y

# 2. Download and Setup Instance 1
cd /tmp
wget https://dist.neo4j.org/neo4j-community-5.15.0-unix.tar.gz
tar -xzf neo4j-community-5.15.0-unix.tar.gz
sudo mkdir -p /opt/neo4j-instance1
sudo mv neo4j-community-5.15.0/* /opt/neo4j-instance1/
sudo chown -R $USER:$USER /opt/neo4j-instance1

# 3. Download and Setup Instance 2
cd /tmp
wget https://dist.neo4j.org/neo4j-community-5.15.0-unix.tar.gz -O neo4j-2.tar.gz
tar -xzf neo4j-2.tar.gz
sudo mkdir -p /opt/neo4j-instance2
sudo mv neo4j-community-5.15.0/* /opt/neo4j-instance2/
sudo chown -R $USER:$USER /opt/neo4j-instance2

# 4. Create custom data directories
mkdir -p /home/ubuntu/openmailbot/openmailbot/agent/data/ankitgoel2004@gmail.com/graph_db
mkdir -p /home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/graph_db
chmod -R 755 /home/ubuntu/openmailbot/openmailbot/agent/data/

# 5. Configure Instance 1
cat >> /opt/neo4j-instance1/conf/neo4j.conf << 'EOF'

# Custom data directory for user 1
server.directories.data=/home/ubuntu/openmailbot/openmailbot/agent/data/ankitgoel2004@gmail.com/graph_db

# Ports for instance 1
server.bolt.listen_address=:7687
server.http.listen_address=:7474
server.bolt.advertised_address=:7687
server.http.advertised_address=:7474

# Initial password setting
dbms.security.auth_enabled=true
EOF

# 6. Configure Instance 2
cat >> /opt/neo4j-instance2/conf/neo4j.conf << 'EOF'

# Custom data directory for user 2
server.directories.data=/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/graph_db

# Ports for instance 2 (different from instance 1)
server.bolt.listen_address=:7688
server.http.listen_address=:7475
server.bolt.advertised_address=:7688
server.http.advertised_address=:7475

# Initial password setting
dbms.security.auth_enabled=true
EOF

# 7. Start Instance 1
/opt/neo4j-instance1/bin/neo4j start

# 8. Start Instance 2
/opt/neo4j-instance2/bin/neo4j start

# 9. Verify both instances are running
ps aux | grep neo4j

# 10. Check the logs
tail -f /opt/neo4j-instance1/logs/neo4j.log
# Press Ctrl+C to exit, then check instance 2
tail -f /opt/neo4j-instance2/logs/neo4j.log

# 11. Set initial passwords (after instances start)
# For Instance 1 (port 7687):
/opt/neo4j-instance1/bin/cypher-shell -a bolt://localhost:7687 -u neo4j -p neo4j
# Then run: ALTER USER neo4j SET PASSWORD 'your_password_1';
# Type :exit to quit

# For Instance 2 (port 7688):
/opt/neo4j-instance2/bin/cypher-shell -a bolt://localhost:7688 -u neo4j -p neo4j
# Then run: ALTER USER neo4j SET PASSWORD 'your_password_2';
# Type :exit to quit