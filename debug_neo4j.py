from neo4j import GraphDatabase
import config

try:
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    print("SUCCESS: Connected to Neo4j")
    driver.close()
except Exception as e:
    print(f"FAILURE: {e}")
