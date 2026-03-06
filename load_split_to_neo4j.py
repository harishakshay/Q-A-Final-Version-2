"""
============================================================
load_split_to_neo4j.py — Knowledge Graph Builder from split.json
============================================================
Reads split.json, extracts entities (concepts, persons, tools)
from the text using curated keyword dictionaries, and loads a
rich knowledge graph into Neo4j with 6 node types and 10
relationship types.

Node Types: Document, Chunk, Category, Concept, Person, Tool
============================================================
"""

import json
import re
import sys
import os
from collections import defaultdict

sys.path.append(os.getcwd())

from neo4j import GraphDatabase
import config

# ============================================================
# ENTITY DICTIONARIES — curated from split.json content
# ============================================================

# { display_name: { type, aliases (for matching), description } }
CONCEPTS = {
    # Frameworks
    "RICE Framework": {"type": "Framework", "aliases": ["RICE", "Reach, Impact, Confidence, Effort"]},
    "MoSCoW Framework": {"type": "Framework", "aliases": ["MoSCoW", "Must-have, Should-have, Could-have"]},
    "Kano Model": {"type": "Framework", "aliases": ["Kano model"]},
    "Jobs-to-be-Done": {"type": "Framework", "aliases": ["JTBD", "Jobs-to-be-Done"]},
    "OKRs": {"type": "Framework", "aliases": ["OKRs", "Objectives and Key Results"]},
    "Stage-Gate Model": {"type": "Framework", "aliases": ["Stage-Gate"]},
    "INVEST Criteria": {"type": "Framework", "aliases": ["INVEST criteria", "INVEST"]},
    "SERVQUAL": {"type": "Framework", "aliases": ["SERVQUAL"]},
    "Gaps Model": {"type": "Framework", "aliases": ["Gaps Model"]},
    "Porter's Five Forces": {"type": "Framework", "aliases": ["Five Forces", "Porter's Five Forces"]},
    "SWOT Analysis": {"type": "Framework", "aliases": ["SWOT analysis", "SWOT"]},
    "TOWS Matrix": {"type": "Framework", "aliases": ["TOWS matrix", "TOWS"]},
    "STP Marketing": {"type": "Framework", "aliases": ["STP", "Segmentation, Targeting, and Positioning"]},
    "BCG Growth-Share Matrix": {"type": "Framework", "aliases": ["BCG", "Growth-Share Matrix"]},
    "PESTEL Analysis": {"type": "Framework", "aliases": ["PESTEL"]},
    "4Ps Marketing Mix": {"type": "Framework", "aliases": ["4Ps", "marketing mix", "4Ps framework"]},
    "7Ps Framework": {"type": "Framework", "aliases": ["7Ps"]},
    "Value Net Framework": {"type": "Framework", "aliases": ["Value Net"]},
    "Design Thinking": {"type": "Framework", "aliases": ["Design thinking"]},
    "Lean Startup": {"type": "Framework", "aliases": ["Lean Startup"]},
    "Agile Manifesto": {"type": "Framework", "aliases": ["Agile Manifesto"]},
    "Service-Profit Chain": {"type": "Framework", "aliases": ["Service-Profit Chain"]},
    "Gartner Hype Cycle": {"type": "Framework", "aliases": ["Hype Cycle"]},
    "CBBE Pyramid": {"type": "Framework", "aliases": ["CBBE", "Customer-Based Brand Equity"]},
    "Aaker Brand Equity Model": {"type": "Framework", "aliases": ["Aaker's brand equity"]},
    "Box-Jenkins Methodology": {"type": "Framework", "aliases": ["Box-Jenkins"]},
    "ETS Framework": {"type": "Framework", "aliases": ["ETS framework", "Error, Trend, Seasonality"]},

    # Metrics
    "Net Promoter Score": {"type": "Metric", "aliases": ["NPS", "Net Promoter Score"]},
    "Customer Satisfaction Score": {"type": "Metric", "aliases": ["CSAT", "Customer Satisfaction Score"]},
    "Customer Effort Score": {"type": "Metric", "aliases": ["CES", "Customer Effort Score"]},
    "Customer Lifetime Value": {"type": "Metric", "aliases": ["CLV", "Customer Lifetime Value"]},
    "Customer Acquisition Cost": {"type": "Metric", "aliases": ["CAC", "Customer Acquisition Cost"]},
    "Churn Rate": {"type": "Metric", "aliases": ["churn rate", "customer attrition rate"]},
    "Daily Active Users": {"type": "Metric", "aliases": ["DAU", "Daily Active Users"]},
    "Monthly Active Users": {"type": "Metric", "aliases": ["MAU", "Monthly Active Users"]},
    "First Contact Resolution": {"type": "Metric", "aliases": ["FCR", "First Contact Resolution"]},
    "Average Handle Time": {"type": "Metric", "aliases": ["AHT", "Average Handle Time"]},
    "Velocity": {"type": "Metric", "aliases": ["Velocity"]},
    "Price Elasticity": {"type": "Metric", "aliases": ["Price elasticity", "price elasticity of demand"]},
    "Mean Absolute Percentage Error": {"type": "Metric", "aliases": ["MAPE"]},
    "Root Mean Squared Error": {"type": "Metric", "aliases": ["RMSE"]},
    "Mean Absolute Error": {"type": "Metric", "aliases": ["MAE", "Mean Absolute Error"]},

    # Models / Methods
    "ARIMA": {"type": "Model", "aliases": ["ARIMA", "AutoRegressive Integrated Moving Average"]},
    "SARIMA": {"type": "Model", "aliases": ["SARIMA"]},
    "Exponential Smoothing": {"type": "Model", "aliases": ["Exponential smoothing", "exponential smoothing"]},
    "Holt-Winters": {"type": "Model", "aliases": ["Holt-Winters", "triple exponential smoothing"]},
    "Simple Moving Average": {"type": "Model", "aliases": ["SMA", "Simple Moving Average"]},
    "Exponential Moving Average": {"type": "Model", "aliases": ["EMA", "Exponential Moving Average"]},
    "MACD": {"type": "Model", "aliases": ["MACD", "Moving average convergence divergence"]},
    "Prophet": {"type": "Model", "aliases": ["Prophet"]},
    "TBATS": {"type": "Model", "aliases": ["TBATS"]},
    "Isolation Forest": {"type": "Model", "aliases": ["Isolation Forest"]},
    "Autoencoder": {"type": "Model", "aliases": ["Autoencoder", "Autoencoders"]},
    "LSTM": {"type": "Model", "aliases": ["LSTM", "Long Short-Term Memory"]},
    "STL Decomposition": {"type": "Model", "aliases": ["STL decomposition", "STL"]},
    "Mann-Kendall Test": {"type": "Method", "aliases": ["Mann-Kendall"]},
    "Augmented Dickey-Fuller Test": {"type": "Method", "aliases": ["Augmented Dickey-Fuller", "ADF test"]},
    "Conjoint Analysis": {"type": "Method", "aliases": ["Conjoint analysis", "conjoint analysis"]},
    "A/B Testing": {"type": "Method", "aliases": ["A/B testing", "split testing"]},
    "Delphi Method": {"type": "Method", "aliases": ["Delphi method"]},
    "Story Mapping": {"type": "Method", "aliases": ["Story mapping"]},

    # Strategies
    "Penetration Pricing": {"type": "Strategy", "aliases": ["Penetration pricing", "penetration pricing"]},
    "Price Skimming": {"type": "Strategy", "aliases": ["Price skimming", "price skimming"]},
    "Freemium": {"type": "Strategy", "aliases": ["Freemium", "freemium"]},
    "Dynamic Pricing": {"type": "Strategy", "aliases": ["Dynamic pricing", "dynamic pricing"]},
    "Value-Based Pricing": {"type": "Strategy", "aliases": ["Value-based pricing", "value-based pricing"]},
    "Cost-Based Pricing": {"type": "Strategy", "aliases": ["Cost-based pricing", "Cost-plus pricing"]},
    "Bundling": {"type": "Strategy", "aliases": ["Bundling", "bundling"]},
    "Subscription Pricing": {"type": "Strategy", "aliases": ["Subscription pricing"]},
    "Usage-Based Pricing": {"type": "Strategy", "aliases": ["Usage-based pricing", "consumption pricing"]},
    "Premium Pricing": {"type": "Strategy", "aliases": ["Premium pricing", "Prestige pricing"]},
    "Product-Led Growth": {"type": "Strategy", "aliases": ["PLG", "product-led growth"]},
    "Inbound Marketing": {"type": "Strategy", "aliases": ["Inbound marketing"]},
    "Content Marketing": {"type": "Strategy", "aliases": ["Content marketing"]},

    # Concepts
    "Product Lifecycle": {"type": "Concept", "aliases": ["product lifecycle", "PLC"]},
    "MVP": {"type": "Concept", "aliases": ["MVP", "Minimum Viable Product"]},
    "Build-Measure-Learn": {"type": "Concept", "aliases": ["Build-Measure-Learn"]},
    "User Story": {"type": "Concept", "aliases": ["user story", "user stories"]},
    "Product Backlog": {"type": "Concept", "aliases": ["product backlog"]},
    "Sprint": {"type": "Concept", "aliases": ["sprint", "sprints"]},
    "Scrum": {"type": "Concept", "aliases": ["Scrum"]},
    "Kanban": {"type": "Concept", "aliases": ["Kanban"]},
    "Continuous Integration": {"type": "Concept", "aliases": ["CI", "Continuous Integration"]},
    "Continuous Delivery": {"type": "Concept", "aliases": ["CD", "Continuous Delivery"]},
    "Test-Driven Development": {"type": "Concept", "aliases": ["TDD", "Test-Driven Development"]},
    "Brand Equity": {"type": "Concept", "aliases": ["Brand equity", "brand equity"]},
    "Customer Journey": {"type": "Concept", "aliases": ["customer journey"]},
    "Omnichannel": {"type": "Concept", "aliases": ["omnichannel", "Omnichannel"]},
    "Voice of the Customer": {"type": "Concept", "aliases": ["VoC", "Voice of the Customer"]},
    "Service Recovery Paradox": {"type": "Concept", "aliases": ["service recovery paradox"]},
    "Stationarity": {"type": "Concept", "aliases": ["stationarity", "Stationarity"]},
    "Autocorrelation": {"type": "Concept", "aliases": ["Autocorrelation", "autocorrelation"]},
    "Seasonality": {"type": "Concept", "aliases": ["Seasonality", "seasonality"]},
    "Anomaly Detection": {"type": "Concept", "aliases": ["Anomaly detection", "anomaly detection"]},
    "Market Segmentation": {"type": "Concept", "aliases": ["Market segmentation", "market segmentation"]},
    "Brand Architecture": {"type": "Concept", "aliases": ["Brand architecture"]},
    "Total Addressable Market": {"type": "Concept", "aliases": ["TAM", "Total Addressable Market"]},

    # Topic-level concepts (fill zero-entity chunk gaps)
    "Product Roadmap": {"type": "Concept", "aliases": ["product roadmap", "roadmap"]},
    "Customer Loyalty": {"type": "Concept", "aliases": ["customer loyalty", "Customer loyalty"]},
    "Customer Support": {"type": "Concept", "aliases": ["customer support", "Customer support"]},
    "Customer Retention": {"type": "Concept", "aliases": ["customer retention", "Customer retention"]},
    "Price Discrimination": {"type": "Concept", "aliases": ["price discrimination", "Price discrimination"]},
    "Psychological Pricing": {"type": "Concept", "aliases": ["psychological pricing", "Psychological pricing"]},
    "Prestige Pricing": {"type": "Strategy", "aliases": ["prestige pricing"]},
    "Market Research": {"type": "Concept", "aliases": ["market research", "Market research"]},
    "Competitive Analysis": {"type": "Concept", "aliases": ["competitive analysis", "Competitive analysis"]},
    "Competitive Intelligence": {"type": "Concept", "aliases": ["competitive intelligence", "Competitive intelligence"]},
    "Time Series": {"type": "Concept", "aliases": ["time series", "Time series"]},
    "Trend Analysis": {"type": "Concept", "aliases": ["trend analysis", "Trend analysis"]},
    "Brand Management": {"type": "Concept", "aliases": ["brand management", "Brand management"]},
    "Brand Guidelines": {"type": "Concept", "aliases": ["brand guidelines", "Brand guidelines"]},
    "Customer Experience": {"type": "Concept", "aliases": ["customer experience", "Customer experience"]},
    "Requirements Engineering": {"type": "Concept", "aliases": ["requirements engineering"]},

    # Domain-specific pricing concepts
    "Yield Management": {"type": "Concept", "aliases": ["yield management", "Yield management"]},
    "Revenue Management": {"type": "Concept", "aliases": ["revenue management", "Revenue management"]},
    "Loyalty Program": {"type": "Concept", "aliases": ["loyalty program", "Loyalty program", "loyalty programs"]},
    "Decoy Pricing": {"type": "Strategy", "aliases": ["decoy pricing", "Decoy pricing"]},
    "Charm Pricing": {"type": "Strategy", "aliases": ["charm pricing", "odd-even pricing"]},
    "Price Anchoring": {"type": "Concept", "aliases": ["price anchoring", "Price anchoring", "anchor price"]},
    "Reservation Price": {"type": "Concept", "aliases": ["reservation price", "willingness to pay"]},
    "Volume Discount": {"type": "Concept", "aliases": ["volume discount", "volume discounts", "Volume discount"]},
    "Consumer Surplus": {"type": "Concept", "aliases": ["consumer surplus", "Consumer surplus"]},
    "Market Entry Strategy": {"type": "Strategy", "aliases": ["market entry", "Market entry"]},

    # Support and operations concepts
    "Tiered Support": {"type": "Concept", "aliases": ["tiered support", "support tiers", "Tiered support"]},
    "Self-Service Support": {"type": "Concept", "aliases": ["self-service", "Self-service"]},
    "Knowledge Base": {"type": "Concept", "aliases": ["knowledge base", "Knowledge base"]},
    "Service Level Agreement": {"type": "Concept", "aliases": ["SLA", "service level agreement"]},
    "Win-Loss Analysis": {"type": "Concept", "aliases": ["win-loss", "Win-loss"]},
    "Stakeholder Alignment": {"type": "Concept", "aliases": ["stakeholder alignment", "stakeholders"]},

    # Analytics and forecasting concepts
    "Seasonal Index": {"type": "Concept", "aliases": ["seasonal index", "Seasonal index", "seasonal indices"]},
    "Demand Forecasting": {"type": "Concept", "aliases": ["demand forecasting", "Demand forecasting"]},
    "Statistical Process Control": {"type": "Concept", "aliases": ["statistical process control", "process control"]},
    "Control Chart": {"type": "Concept", "aliases": ["control chart", "Control chart", "control charts"]},
    "Cross-Sectional Data": {"type": "Concept", "aliases": ["cross-sectional data"]},
}

PERSONS = {
    "Eric Ries": {"contribution": "Lean Startup / MVP", "aliases": ["Eric Ries"]},
    "Michael Porter": {"contribution": "Competitive Strategy / Five Forces", "aliases": ["Michael E. Porter", "Michael Porter", "Porter"]},
    "Fred Reichheld": {"contribution": "Net Promoter Score", "aliases": ["Fred Reichheld", "Reichheld"]},
    "Philip Kotler": {"contribution": "Marketing Strategy / STP", "aliases": ["Philip Kotler", "Kotler"]},
    "Theodore Levitt": {"contribution": "Product Lifecycle", "aliases": ["Theodore Levitt", "Levitt"]},
    "Robert Cooper": {"contribution": "Stage-Gate Model", "aliases": ["Robert Cooper", "Dr. Robert Cooper"]},
    "Kent Beck": {"contribution": "Extreme Programming / User Stories", "aliases": ["Kent Beck"]},
    "Mike Cohn": {"contribution": "User Story Template", "aliases": ["Mike Cohn"]},
    "Jeff Patton": {"contribution": "Story Mapping", "aliases": ["Jeff Patton"]},
    "Daniel Kahneman": {"contribution": "Behavioral Economics", "aliases": ["Daniel Kahneman"]},
    "Amos Tversky": {"contribution": "Behavioral Economics", "aliases": ["Amos Tversky"]},
    "Richard Thaler": {"contribution": "Behavioral Economics / Nudge Theory", "aliases": ["Richard Thaler"]},
    "David Aaker": {"contribution": "Brand Equity Model", "aliases": ["David Aaker", "Aaker"]},
    "Kevin Lane Keller": {"contribution": "CBBE Pyramid", "aliases": ["Kevin Lane Keller", "Keller"]},
    "George Box": {"contribution": "ARIMA / Box-Jenkins", "aliases": ["George Box"]},
    "Gwilym Jenkins": {"contribution": "Box-Jenkins Methodology", "aliases": ["Gwilym Jenkins"]},
    "Charles Holt": {"contribution": "Double Exponential Smoothing", "aliases": ["Charles Holt"]},
    "Peter Winters": {"contribution": "Holt-Winters Method", "aliases": ["Peter Winters"]},
    "Robert Brown": {"contribution": "Exponential Smoothing", "aliases": ["Robert Brown"]},
    "Spyros Makridakis": {"contribution": "M-Competitions", "aliases": ["Spyros Makridakis"]},
    "Wendell Smith": {"contribution": "Market Segmentation", "aliases": ["Wendell Smith"]},
    "Albert Humphrey": {"contribution": "SWOT Analysis", "aliases": ["Albert Humphrey"]},
    "Richard Oliver": {"contribution": "Expectancy-Disconfirmation Theory", "aliases": ["Richard Oliver"]},
    "Steve Blank": {"contribution": "Customer Development", "aliases": ["Steve Blank"]},
    "Ron Jeffries": {"contribution": "Three Cs of User Stories", "aliases": ["Ron Jeffries"]},
    "Fred Wilson": {"contribution": "Freemium Term", "aliases": ["Fred Wilson"]},
}

TOOLS = {
    "Mixpanel": {"purpose": "Product Analytics", "aliases": ["Mixpanel"]},
    "Amplitude": {"purpose": "Product Analytics", "aliases": ["Amplitude"]},
    "Pendo": {"purpose": "Product Analytics / In-app Feedback", "aliases": ["Pendo"]},
    "Jira": {"purpose": "Project Management", "aliases": ["Jira"]},
    "GitHub": {"purpose": "Version Control / Development", "aliases": ["GitHub"]},
    "Productboard": {"purpose": "Product Roadmapping", "aliases": ["Productboard"]},
    "Aha!": {"purpose": "Product Roadmapping", "aliases": ["Aha!"]},
    "Roadmunk": {"purpose": "Product Roadmapping", "aliases": ["Roadmunk"]},
    "Linear": {"purpose": "Project Management", "aliases": ["Linear"]},
    "Notion": {"purpose": "Collaboration", "aliases": ["Notion"]},
    "Hotjar": {"purpose": "User Feedback / Heatmaps", "aliases": ["Hotjar"]},
    "Intercom": {"purpose": "Customer Messaging", "aliases": ["Intercom"]},
    "Gainsight": {"purpose": "Customer Success", "aliases": ["Gainsight"]},
    "Totango": {"purpose": "Customer Success", "aliases": ["Totango"]},
    "ChurnZero": {"purpose": "Customer Success", "aliases": ["ChurnZero"]},
    "HubSpot": {"purpose": "Inbound Marketing / CRM", "aliases": ["HubSpot"]},
    "Slack": {"purpose": "Team Communication", "aliases": ["Slack"]},
    "Zoom": {"purpose": "Video Conferencing", "aliases": ["Zoom"]},
    "Figma": {"purpose": "Design Collaboration", "aliases": ["Figma"]},
    "Azure DevOps": {"purpose": "DevOps Platform", "aliases": ["Azure DevOps"]},
    "IBM DOORS": {"purpose": "Requirements Management", "aliases": ["IBM DOORS"]},
    "Brandwatch": {"purpose": "Social Listening", "aliases": ["Brandwatch"]},
    "Sprout Social": {"purpose": "Social Media Management", "aliases": ["Sprout Social"]},
    "G2": {"purpose": "Software Review Platform", "aliases": ["G2"]},
    "Trustpilot": {"purpose": "Review Platform", "aliases": ["Trustpilot"]},
    "Capterra": {"purpose": "Software Review Platform", "aliases": ["Capterra"]},
    "Calendly": {"purpose": "Scheduling", "aliases": ["Calendly"]},
    "Atlassian": {"purpose": "Software Development Suite", "aliases": ["Atlassian"]},
    "AWS": {"purpose": "Cloud Infrastructure", "aliases": ["AWS"]},
    "Google Cloud": {"purpose": "Cloud Infrastructure", "aliases": ["Google Cloud"]},
    "XGBoost": {"purpose": "Machine Learning", "aliases": ["XGBoost"]},
    "LightGBM": {"purpose": "Machine Learning", "aliases": ["LightGBM"]},
}

# Cross-concept relationships (manually curated semantic links)
CONCEPT_RELATIONS = [
    ("Net Promoter Score", "Customer Satisfaction Score", "complementary metric"),
    ("Net Promoter Score", "Customer Effort Score", "complementary metric"),
    ("Net Promoter Score", "Churn Rate", "loyalty indicator vs attrition"),
    ("Customer Lifetime Value", "Customer Acquisition Cost", "unit economics pair"),
    ("Customer Lifetime Value", "Churn Rate", "retention drives CLV"),
    ("Churn Rate", "Customer Satisfaction Score", "satisfaction prevents churn"),
    ("MVP", "Build-Measure-Learn", "core feedback loop"),
    ("MVP", "Lean Startup", "founding concept"),
    ("User Story", "Product Backlog", "backlog composition"),
    ("User Story", "Sprint", "sprint work units"),
    ("Scrum", "Sprint", "Scrum organizes sprints"),
    ("Scrum", "Kanban", "alternative agile methods"),
    ("Agile Manifesto", "Scrum", "Scrum implements Agile"),
    ("Agile Manifesto", "Kanban", "Kanban implements Agile"),
    ("Continuous Integration", "Continuous Delivery", "CI feeds CD"),
    ("Continuous Integration", "Test-Driven Development", "TDD enables CI"),
    ("Product Lifecycle", "Stage-Gate Model", "lifecycle management framework"),
    ("Product Lifecycle", "BCG Growth-Share Matrix", "portfolio lifecycle analysis"),
    ("Penetration Pricing", "Price Skimming", "opposing launch strategies"),
    ("Freemium", "Product-Led Growth", "PLG uses freemium"),
    ("Dynamic Pricing", "Price Elasticity", "elasticity drives dynamic pricing"),
    ("Value-Based Pricing", "Customer Lifetime Value", "CLV informs value pricing"),
    ("ARIMA", "Exponential Smoothing", "competing time series models"),
    ("ARIMA", "SARIMA", "seasonal extension"),
    ("Holt-Winters", "Exponential Smoothing", "Holt-Winters extends ES"),
    ("Seasonality", "Holt-Winters", "Holt-Winters models seasonality"),
    ("Seasonality", "TBATS", "TBATS handles multiple seasonalities"),
    ("Stationarity", "ARIMA", "ARIMA requires stationarity"),
    ("Anomaly Detection", "Isolation Forest", "detection algorithm"),
    ("Anomaly Detection", "LSTM", "deep learning detector"),
    ("SWOT Analysis", "TOWS Matrix", "TOWS extends SWOT"),
    ("SWOT Analysis", "Porter's Five Forces", "complementary strategic tools"),
    ("STP Marketing", "Market Segmentation", "segmentation is STP step 1"),
    ("Brand Equity", "Brand Architecture", "architecture protects equity"),
    ("SERVQUAL", "First Contact Resolution", "service quality metric"),
    ("Content Marketing", "Inbound Marketing", "content drives inbound"),
    ("Voice of the Customer", "Customer Satisfaction Score", "VoC measures CSAT"),
    ("Story Mapping", "User Story", "organizes user stories"),
    ("A/B Testing", "MVP", "testing validates MVP hypotheses"),
    ("Product Backlog", "RICE Framework", "RICE prioritizes backlog"),
    ("Product Backlog", "MoSCoW Framework", "MoSCoW prioritizes backlog"),
    ("Total Addressable Market", "Market Segmentation", "TAM requires segmentation"),
    ("Simple Moving Average", "Exponential Moving Average", "SMA vs EMA variants"),
    ("Box-Jenkins Methodology", "ARIMA", "Box-Jenkins builds ARIMA"),
    ("ETS Framework", "Exponential Smoothing", "ETS taxonomy for ES models"),

    # New relationships for added concepts
    ("Product Roadmap", "Sprint", "roadmap feeds sprints"),
    ("Customer Loyalty", "Customer Lifetime Value", "loyalty drives CLV"),
    ("Customer Support", "First Contact Resolution", "FCR is key support metric"),
    ("Price Discrimination", "Consumer Surplus", "captures consumer surplus"),
    ("Psychological Pricing", "Price Anchoring", "anchoring is psychological tactic"),
    ("Market Research", "Conjoint Analysis", "conjoint is research method"),
    ("Competitive Analysis", "SWOT Analysis", "SWOT supports competitive analysis"),
    ("Time Series", "Seasonality", "seasonality is time series component"),
    ("Trend Analysis", "Mann-Kendall Test", "Mann-Kendall detects trends"),
    ("Brand Management", "Brand Equity", "management preserves equity"),
    ("Customer Experience", "Customer Journey", "journey maps CX"),
    ("Dynamic Pricing", "Yield Management", "yield management is dynamic pricing"),
    ("Demand Forecasting", "ARIMA", "ARIMA for demand forecasting"),
    ("Loyalty Program", "Customer Loyalty", "programs build loyalty"),
]

# Person → Concept they created
PERSON_CREATED_CONCEPT = [
    ("Eric Ries", "MVP"),
    ("Eric Ries", "Lean Startup"),
    ("Eric Ries", "Build-Measure-Learn"),
    ("Michael Porter", "Porter's Five Forces"),
    ("Fred Reichheld", "Net Promoter Score"),
    ("Philip Kotler", "STP Marketing"),
    ("Theodore Levitt", "Product Lifecycle"),
    ("Robert Cooper", "Stage-Gate Model"),
    ("Kent Beck", "User Story"),
    ("Mike Cohn", "User Story"),
    ("Jeff Patton", "Story Mapping"),
    ("Daniel Kahneman", "A/B Testing"),
    ("David Aaker", "Brand Equity"),
    ("David Aaker", "Aaker Brand Equity Model"),
    ("Kevin Lane Keller", "CBBE Pyramid"),
    ("George Box", "ARIMA"),
    ("George Box", "Box-Jenkins Methodology"),
    ("Gwilym Jenkins", "Box-Jenkins Methodology"),
    ("Charles Holt", "Exponential Smoothing"),
    ("Peter Winters", "Holt-Winters"),
    ("Albert Humphrey", "SWOT Analysis"),
    ("Wendell Smith", "Market Segmentation"),
    ("Richard Oliver", "Customer Satisfaction Score"),
    ("Steve Blank", "MVP"),
    ("Fred Wilson", "Freemium"),
]

# Tool → Concept it implements
TOOL_IMPLEMENTS_CONCEPT = [
    ("Mixpanel", "Daily Active Users"),
    ("Amplitude", "Daily Active Users"),
    ("Gainsight", "Churn Rate"),
    ("Totango", "Churn Rate"),
    ("ChurnZero", "Churn Rate"),
    ("Jira", "Product Backlog"),
    ("Jira", "Sprint"),
    ("Pendo", "Voice of the Customer"),
    ("Hotjar", "Voice of the Customer"),
    ("HubSpot", "Inbound Marketing"),
    ("Productboard", "OKRs"),
    ("XGBoost", "Anomaly Detection"),
    ("AWS", "Usage-Based Pricing"),
    ("Google Cloud", "Usage-Based Pricing"),
]


# ============================================================
# ENTITY EXTRACTION
# ============================================================

def extract_entities(text, entity_dict):
    """Find which entities from the dictionary appear in the text."""
    found = set()
    for name, info in entity_dict.items():
        for alias in info["aliases"]:
            # Use word boundary matching for short aliases, substring for longer ones
            if len(alias) <= 3:
                # For short acronyms like NPS, DAU, use word boundaries
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, text):
                    found.add(name)
                    break
            else:
                if alias in text:
                    found.add(name)
                    break
    return found


# ============================================================
# NEO4J LOADING
# ============================================================

def load_to_neo4j(split_data):
    """Load all nodes and relationships into Neo4j."""
    
    print("\n[1/8] Connecting to Neo4j...")
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    print("  ✓ Connected successfully")
    
    # Clear existing graph
    print("\n[2/8] Clearing existing graph...")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("  ✓ Graph cleared")
    
    # Create constraints and indexes
    print("\n[3/8] Creating constraints and indexes...")
    with driver.session() as session:
        constraints = [
            "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (cat:Category) REQUIRE cat.name IS UNIQUE",
            "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (con:Concept) REQUIRE con.name IS UNIQUE",
            "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT tool_name IF NOT EXISTS FOR (t:Tool) REQUIRE t.name IS UNIQUE",
        ]
        for c in constraints:
            try:
                session.run(c)
            except Exception as e:
                print(f"  Warning: {e}")
    print("  ✓ Constraints created")
    
    # Collect unique documents and categories
    documents = {}  # parent_post_id -> title
    categories = set()
    doc_chunks = defaultdict(list)  # parent_post_id -> [chunk_ids in order]
    all_concept_mentions = defaultdict(set)  # chunk_id -> set of concept names
    all_person_mentions = defaultdict(set)
    all_tool_mentions = defaultdict(set)
    
    print("\n[4/8] Extracting entities from all chunks...")
    for item in split_data:
        meta = item["metadata"]
        doc_id = meta.get("parent_post_id", "")
        title = meta.get("title", "")
        documents[doc_id] = title
        
        # Parse categories
        cats_raw = meta.get("categories", "[]")
        if isinstance(cats_raw, str):
            try:
                cats = json.loads(cats_raw)
            except:
                cats = [cats_raw]
        else:
            cats = cats_raw
        for c in cats:
            categories.add(c)
        
        # Track chunk ordering within document
        doc_chunks[doc_id].append(item["id"])
        
        # Extract entities from text
        text = item["document"]
        all_concept_mentions[item["id"]] = extract_entities(text, CONCEPTS)
        all_person_mentions[item["id"]] = extract_entities(text, PERSONS)
        all_tool_mentions[item["id"]] = extract_entities(text, TOOLS)
    
    # Count entities found
    all_concepts_found = set()
    all_persons_found = set()
    all_tools_found = set()
    for v in all_concept_mentions.values():
        all_concepts_found.update(v)
    for v in all_person_mentions.values():
        all_persons_found.update(v)
    for v in all_tool_mentions.values():
        all_tools_found.update(v)
    
    print(f"  ✓ Found {len(all_concepts_found)} concepts, {len(all_persons_found)} persons, {len(all_tools_found)} tools")
    
    # Create Document nodes
    print("\n[5/8] Creating Document and Category nodes...")
    with driver.session() as session:
        for doc_id, title in documents.items():
            session.run(
                "MERGE (d:Document {id: $id}) SET d.title = $title",
                {"id": doc_id, "title": title}
            )
        for cat_name in categories:
            session.run(
                "MERGE (cat:Category {name: $name})",
                {"name": cat_name}
            )
    print(f"  ✓ Created {len(documents)} Document nodes, {len(categories)} Category nodes")
    
    # Create Chunk nodes + relationships
    print("\n[6/8] Creating Chunk nodes and basic relationships...")
    with driver.session() as session:
        for item in split_data:
            meta = item["metadata"]
            chunk_id = item["id"]
            doc_id = meta.get("parent_post_id", "")
            
            # Create Chunk
            session.run("""
                MERGE (c:Chunk {id: $id})
                SET c.section_heading = $section_heading,
                    c.text = $text,
                    c.type = $type,
                    c.source = $source
            """, {
                "id": chunk_id,
                "section_heading": meta.get("section_heading", ""),
                "text": item["document"],
                "type": meta.get("type", ""),
                "source": meta.get("source", ""),
            })
            
            # Chunk -> Document
            session.run("""
                MATCH (c:Chunk {id: $cid})
                MATCH (d:Document {id: $did})
                MERGE (c)-[:BELONGS_TO]->(d)
            """, {"cid": chunk_id, "did": doc_id})
            
            # Chunk -> Category
            cats_raw = meta.get("categories", "[]")
            if isinstance(cats_raw, str):
                try:
                    cats = json.loads(cats_raw)
                except:
                    cats = [cats_raw]
            else:
                cats = cats_raw
            for cat_name in cats:
                session.run("""
                    MATCH (c:Chunk {id: $cid})
                    MATCH (cat:Category {name: $cat})
                    MERGE (c)-[:CATEGORIZED_AS]->(cat)
                """, {"cid": chunk_id, "cat": cat_name})
                
                # Document -> Category
                session.run("""
                    MATCH (d:Document {id: $did})
                    MATCH (cat:Category {name: $cat})
                    MERGE (d)-[:CATEGORIZED_AS]->(cat)
                """, {"did": doc_id, "cat": cat_name})
    
    print(f"  ✓ Created {len(split_data)} Chunk nodes with BELONGS_TO and CATEGORIZED_AS relationships")
    
    # Create NEXT_CHUNK relationships (sequential reading order)
    with driver.session() as session:
        next_count = 0
        for doc_id, chunk_ids in doc_chunks.items():
            for i in range(len(chunk_ids) - 1):
                session.run("""
                    MATCH (c1:Chunk {id: $id1})
                    MATCH (c2:Chunk {id: $id2})
                    MERGE (c1)-[:NEXT_CHUNK]->(c2)
                """, {"id1": chunk_ids[i], "id2": chunk_ids[i + 1]})
                next_count += 1
    print(f"  ✓ Created {next_count} NEXT_CHUNK relationships")
    
    # Create Concept, Person, Tool nodes and MENTIONS relationships
    print("\n[7/8] Creating entity nodes and MENTIONS relationships...")
    with driver.session() as session:
        # Concept nodes
        for concept_name in all_concepts_found:
            info = CONCEPTS[concept_name]
            session.run(
                "MERGE (con:Concept {name: $name}) SET con.type = $type",
                {"name": concept_name, "type": info["type"]}
            )
        
        # Person nodes
        for person_name in all_persons_found:
            info = PERSONS[person_name]
            session.run(
                "MERGE (p:Person {name: $name}) SET p.contribution = $contribution",
                {"name": person_name, "contribution": info["contribution"]}
            )
        
        # Tool nodes
        for tool_name in all_tools_found:
            info = TOOLS[tool_name]
            session.run(
                "MERGE (t:Tool {name: $name}) SET t.purpose = $purpose",
                {"name": tool_name, "purpose": info["purpose"]}
            )
        
        # MENTIONS_CONCEPT relationships
        mentions_count = 0
        for chunk_id, concepts in all_concept_mentions.items():
            for concept_name in concepts:
                session.run("""
                    MATCH (c:Chunk {id: $cid})
                    MATCH (con:Concept {name: $name})
                    MERGE (c)-[:MENTIONS_CONCEPT]->(con)
                """, {"cid": chunk_id, "name": concept_name})
                mentions_count += 1
        
        # MENTIONS_PERSON relationships
        for chunk_id, persons in all_person_mentions.items():
            for person_name in persons:
                session.run("""
                    MATCH (c:Chunk {id: $cid})
                    MATCH (p:Person {name: $name})
                    MERGE (c)-[:MENTIONS_PERSON]->(p)
                """, {"cid": chunk_id, "name": person_name})
                mentions_count += 1
        
        # MENTIONS_TOOL relationships
        for chunk_id, tools in all_tool_mentions.items():
            for tool_name in tools:
                session.run("""
                    MATCH (c:Chunk {id: $cid})
                    MATCH (t:Tool {name: $name})
                    MERGE (c)-[:MENTIONS_TOOL]->(t)
                """, {"cid": chunk_id, "name": tool_name})
                mentions_count += 1
    
    print(f"  ✓ Created {len(all_concepts_found)} Concept, {len(all_persons_found)} Person, {len(all_tools_found)} Tool nodes")
    print(f"  ✓ Created {mentions_count} MENTIONS relationships")
    
    # Create semantic relationships
    print("\n[8/8] Creating semantic relationships (RELATED_TO, CREATED, IMPLEMENTS)...")
    with driver.session() as session:
        rel_count = 0
        
        # RELATED_TO between concepts
        for c1, c2, reason in CONCEPT_RELATIONS:
            if c1 in all_concepts_found and c2 in all_concepts_found:
                session.run("""
                    MATCH (a:Concept {name: $n1})
                    MATCH (b:Concept {name: $n2})
                    MERGE (a)-[r:RELATED_TO]->(b)
                    SET r.reason = $reason
                """, {"n1": c1, "n2": c2, "reason": reason})
                rel_count += 1
        
        # Person CREATED Concept
        for person_name, concept_name in PERSON_CREATED_CONCEPT:
            if person_name in all_persons_found and concept_name in all_concepts_found:
                session.run("""
                    MATCH (p:Person {name: $pname})
                    MATCH (c:Concept {name: $cname})
                    MERGE (p)-[:CREATED]->(c)
                """, {"pname": person_name, "cname": concept_name})
                rel_count += 1
        
        # Tool IMPLEMENTS Concept
        for tool_name, concept_name in TOOL_IMPLEMENTS_CONCEPT:
            if tool_name in all_tools_found and concept_name in all_concepts_found:
                session.run("""
                    MATCH (t:Tool {name: $tname})
                    MATCH (c:Concept {name: $cname})
                    MERGE (t)-[:IMPLEMENTS]->(c)
                """, {"tname": tool_name, "cname": concept_name})
                rel_count += 1
    
    print(f"  ✓ Created {rel_count} semantic relationships")
    
    # Print final statistics
    print("\n" + "=" * 60)
    print("FINAL KNOWLEDGE GRAPH STATISTICS")
    print("=" * 60)
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS type, count(n) AS count
            ORDER BY count DESC
        """)
        print("\nNodes:")
        for record in result:
            print(f"  {record['type']:20s} {record['count']:5d}")
        
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS count
            ORDER BY count DESC
        """)
        print("\nRelationships:")
        for record in result:
            print(f"  {record['rel_type']:25s} {record['count']:5d}")
        
        total_nodes = session.run("MATCH (n) RETURN count(n)").single()[0]
        total_rels = session.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
        print(f"\nTotal: {total_nodes} nodes, {total_rels} relationships")
    
    driver.close()
    print("\n✓ Knowledge graph loaded successfully!")
    print("  View it at: http://localhost:7474")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("KNOWLEDGE GRAPH BUILDER — split.json → Neo4j")
    print("=" * 60)
    
    # Load split.json
    split_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "split.json")
    if not os.path.exists(split_path):
        print(f"Error: {split_path} not found")
        sys.exit(1)
    
    with open(split_path, "r", encoding="utf-8") as f:
        split_data = json.load(f)
    
    print(f"\nLoaded {len(split_data)} chunks from split.json")
    
    # Load to Neo4j
    try:
        load_to_neo4j(split_data)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
