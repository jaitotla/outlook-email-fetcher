# Future Work & Roadmap

This document outlines planned improvements and features that are not yet implemented but are on the roadmap for OpenMailBot.

## 🔐 Security Enhancements

### Rate Limiting
- **Status**: Not implemented
- **Priority**: High
- **Description**: Add rate limiting to all API endpoints to prevent abuse
- **Implementation Notes**:
  - Use `slowapi` or `fastapi-limiter` for agent
  - Use `express-rate-limit` for backend
  - Per-user and per-tenant limits
  - Different limits for different endpoints (e.g., stricter for LLM calls)

### Secrets Management
- **Status**: Partial (using .env files)
- **Priority**: High
- **Description**: Migrate from .env files to a proper secrets manager
- **Options**:
  - HashiCorp Vault
  - AWS Secrets Manager
  - Azure Key Vault
  - Google Cloud Secret Manager
- **Implementation Notes**:
  - API keys should never be stored in plaintext
  - Rotate secrets automatically
  - Audit secret access

### Add-on Endpoint Authentication
- **Status**: Not implemented
- **Priority**: High
- **Description**: Add authentication to `/api/addon/*` endpoints
- **Current State**: These endpoints are exposed without auth
- **Implementation Notes**:
  - Verify Google ID token from Gmail add-on
  - Add HMAC signature verification
  - IP allowlisting for known Google IPs

## 📊 Compliance & Privacy

### GDPR Compliance
- **Status**: Not implemented
- **Priority**: High
- **Description**: Full GDPR compliance for EU users
- **Requirements**:
  - Right to be forgotten (data deletion)
  - Data export functionality
  - Consent management
  - Data processing agreements
  - Cookie consent (for web frontend)

### Data Retention Policies
- **Status**: Not implemented
- **Priority**: Medium
- **Description**: Automatic data cleanup based on retention policies
- **Implementation Notes**:
  - Configurable per-tenant retention periods
  - Auto-delete old embeddings
  - Archive vs. hard delete options

### Audit Trails
- **Status**: Not implemented
- **Priority**: Medium
- **Description**: Comprehensive logging of all user actions
- **Features**:
  - Who accessed what data
  - Settings changes
  - LLM query history
  - Export for compliance audits

## 🏗️ Infrastructure

### CI/CD Pipeline
- **Status**: Not implemented
- **Priority**: High
- **Description**: Automated testing and deployment
- **Components**:
  - GitHub Actions / GitLab CI
  - Automated testing (unit, integration, e2e)
  - Docker image building
  - Kubernetes deployment
  - Staging and production environments

### Backup Strategy
- **Status**: Not implemented
- **Priority**: High
- **Description**: Automated backups for all data stores
- **Requirements**:
  - MongoDB backups (daily snapshots)
  - Vector DB backups
  - Point-in-time recovery
  - Cross-region replication
  - Regular backup testing

### Monitoring & Alerting
- **Status**: Partial (basic health checks)
- **Priority**: Medium
- **Description**: Comprehensive observability
- **Components**:
  - Prometheus metrics
  - Grafana dashboards
  - PagerDuty/Opsgenie integration
  - Log aggregation (ELK/Loki)
  - Distributed tracing (Jaeger)

## 📈 Usage & Analytics

### Usage Tracking
- **Status**: Not implemented
- **Priority**: Medium
- **Description**: Track LLM/embedding usage per user/tenant
- **Features**:
  - Token consumption tracking
  - API call counts
  - Cost estimation
  - Usage quotas and limits
  - Billing integration

### Analytics Dashboard
- **Status**: Not implemented
- **Priority**: Low
- **Description**: Admin dashboard for usage analytics
- **Features**:
  - Per-tenant usage stats
  - Popular features
  - Error rates
  - Response times

## 🔧 Feature Improvements

### Multi-Language Support
- **Status**: Not implemented
- **Priority**: Medium
- **Description**: Support for non-English emails
- **Features**:
  - Language detection
  - Multilingual embeddings
  - Localized UI

### Attachment Processing Improvements
- **Status**: Partial
- **Priority**: Medium
- **Description**: Better handling of attachments
- **Enhancements**:
  - Support more file types (.docx, .xlsx)
  - OCR for images/scanned PDFs
  - Large file chunking
  - Virus scanning

### Team Collaboration
- **Status**: Schema exists, not implemented
- **Priority**: Medium
- **Description**: Shared knowledge base for teams
- **Features**:
  - Shared namespaces
  - Role-based access control
  - Team-wide settings inheritance

## 🔌 Integrations

### Additional Email Providers
- **Status**: Gmail only
- **Priority**: Medium
- **Planned**:
  - Microsoft Outlook (web add-in exists but incomplete)
  - Zoho Mail (extension structure exists)
  - Yahoo Mail
  - IMAP/SMTP generic support

### Calendar Integration
- **Status**: Not implemented
- **Priority**: Low
- **Description**: Detect and handle meeting requests
- **Features**:
  - Extract meeting details from emails
  - Suggest calendar entries
  - Meeting summarization

### CRM Integration
- **Status**: Not implemented
- **Priority**: Low
- **Description**: Connect with CRM systems
- **Planned**:
  - Salesforce
  - HubSpot
  - Pipedrive

## 📋 Technical Debt

### Code Cleanup
- [ ] Remove commented-out code in gmail_summariser.gs
- [ ] Standardize namespace patterns (use `tenantId_userId` everywhere)
- [ ] Unify auth middleware patterns in backend routes
- [ ] Add comprehensive type hints to Python code

### Testing
- [ ] Unit tests for all services
- [ ] Integration tests for API endpoints
- [ ] E2E tests for Gmail add-on
- [ ] Load testing for concurrent users

### Documentation
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Architecture diagrams
- [ ] Deployment guides for different cloud providers
- [ ] User documentation for add-on

---

## Contributing

If you'd like to contribute to any of these features, please:
1. Check if there's an existing issue for the feature
2. Create an issue if none exists
3. Reference this document in your PR

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
