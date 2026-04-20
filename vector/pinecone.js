// Pinecone integration - Node.js client
// Note: Main implementation is in Python agent (agent/vector/pinecone_client.py)
// This is a lightweight wrapper for backend use if needed

const axios = require('axios');

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

module.exports = {
  init: (apiKey, environment) => {
    // Initialization handled by Python agent
    console.log('Pinecone client initialized (via Python agent)');
  },
  
  upsertEmbedding: async (text, metadata, namespace) => {
    try {
      const response = await axios.post(`${AGENT_API_URL}/api/embed`, {
        text,
        userId: metadata.userId,
        tenantId: metadata.tenantId,
        namespace
      });
      return response.data;
    } catch (error) {
      console.error('Error upserting embedding:', error);
      throw error;
    }
  },
  
  queryEmbeddings: async (query, namespace, limit = 10) => {
    try {
      const response = await axios.post(`${AGENT_API_URL}/api/query-embeddings`, {
        query,
        namespace,
        limit
      });
      return response.data;
    } catch (error) {
      console.error('Error querying embeddings:', error);
      throw error;
    }
  }
};
