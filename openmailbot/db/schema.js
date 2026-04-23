// MongoDB schema (simplified)
module.exports = {
  user: {
    id: 'uuid',
    tenant_id: 'uuid',
    first_name: 'string',
    last_name: 'string',
    dob: 'date',
    country: 'string',
    city: 'string',
    email: 'string',
    role: 'admin|manager|employee|solo',
    settings: {
      llm_provider: 'string',
      vector_db: 'string',
      tone: 'string'
    }
  },
  tenant: {
    id: 'uuid',
    name: 'string',
    type: 'enterprise',
    domain: 'string',
    settings: {
      llm_provider: 'string',
      vector_db: 'string'
    }
  },
  group: {
    id: 'uuid',
    tenant_id: 'uuid',
    name: 'string',
    manager_id: 'uuid'
  },
  email_metadata: {
    id: 'uuid',
    tenant_id: 'uuid',
    user_id: 'uuid',
    subject: 'string',
    thread_id: 'string',
    from: 'string',
    to: ['string'],
    timestamp: 'date',
    labels: ['string'],
    embedding_id: 'string',
    summary: 'string'
  }
};
