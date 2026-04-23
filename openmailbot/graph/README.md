# Graph Database Integration

This directory contains graph database clients for managing email thread relationships and contact networks.

## Neo4j Client

**Location**: `agent/graph/neo4j_client.py`

### Features

1. **Email Nodes** - Each email is a node with properties:
   - ID, Thread ID
   - User ID, Tenant ID
   - Subject, From, Timestamp

2. **Contact Nodes** - Contact information:
   - Email address
   - Name (optional)

3. **Relationships**:
   - `IN_THREAD` - Emails in the same thread
   - `REPLIES_TO` - Reply relationships
   - `FROM_CONTACT` - Email from contact
   - `TO_CONTACT` - Email to contact

### Capabilities

- **Find Related Threads** - Discover threads with shared contacts
- **Contact Network** - Visualize user's email network
- **Thread Timeline** - Chronological view of thread emails
- **Network Analysis** - Identify key contacts, communication patterns

### Setup

Requires Neo4j database (local or cloud):
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### Use Cases

1. **Related Thread Discovery** - "Show me other emails with this person"
2. **Contact Insights** - "Who do I email most frequently?"
3. **Thread Context** - "What's the full history of this conversation?"
4. **Network Mapping** - Visualize communication patterns

## Node.js Wrapper

The `graph/neo4j.js` file provides a Node.js wrapper that communicates with the Python agent for graph operations.

## Alternative: NetworkX (Local)

For local/development deployments without Neo4j, NetworkX can be used for basic graph operations (not yet implemented).
