
import config
from neo4j import GraphDatabase

def check_neo4j():
    print(f"Connecting to Neo4j at {config.NEO4J_URI}...")
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI, 
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
        )
        with driver.session() as session:
            # Check connection
            result = session.run("RETURN 1 AS one")
            if result.single()["one"] == 1:
                print("✅ Connection successful!")
            
            # Check Node counts
            node_counts = session.run("MATCH (n) RETURN labels(n) AS label, count(n) AS count")
            print("\nNode Counts:")
            found_nodes = False
            for record in node_counts:
                print(f"  {record['label']}: {record['count']}")
                found_nodes = True
            if not found_nodes:
                print("  (No nodes found in database)")

            # Check Relationship counts
            rel_counts = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")
            print("\nRelationship Counts:")
            found_rels = False
            for record in rel_counts:
                print(f"  {record['type']}: {record['count']}")
                found_rels = True
            if not found_rels:
                print("  (No relationships found in database)")
        
        driver.close()
        return True
    except Exception as e:
        print(f"❌ Error connecting to Neo4j: {e}")
        return False

if __name__ == "__main__":
    check_neo4j()
