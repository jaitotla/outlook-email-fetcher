// Neo4j integration - Node.js client
// Note: Main implementation is in Python agent (agent/graph/neo4j_client.py)
// This is a lightweight wrapper for backend use if needed

const axios = require('axios');

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://localhost:8000';

module.exports = {
  connect: (uri, user, password) => {
    // Connection handled by Python agent
    console.log('Neo4j client initialized (via Python agent)');
  },
  
  addThreadRelation: async (emailId1, emailId2) => {
    try {
      const response = await axios.post(`${AGENT_API_URL}/api/graph/thread-relation`, {
        emailId1,
        emailId2
      });
      return response.data;
    } catch (error) {
      console.error('Error adding thread relation:', error);
      throw error;
    }
  },
  
  getRelatedThreads: async (threadId, userId, tenantId, limit = 5) => {
    try {
      const response = await axios.post(`${AGENT_API_URL}/api/related-threads`, {
        threadId,
        userId,
        tenantId,
        limit
      });
      return response.data.relatedThreadIds || [];
    } catch (error) {
      console.error('Error getting related threads:', error);
      throw error;
    }
  },
  
  getContactNetwork: async (userId, tenantId, limit = 20) => {
    try {
      const response = await axios.get(`${AGENT_API_URL}/api/graph/contacts`, {
        params: { userId, tenantId, limit }
      });
      return response.data;
    } catch (error) {
      console.error('Error getting contact network:', error);
      throw error;
    }
  }
};
