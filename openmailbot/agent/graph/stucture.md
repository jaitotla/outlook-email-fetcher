# Top 10 Universal Email Knowledge Graph Entities & Relationships

## 1. **Person**

**Properties:** Name, Email, Role, Department, Seniority

**Relationships:**
- `SENT` → Email
- `RECEIVED` → Email
- `PARTICIPATES_IN` → Conversation
- `WORKS_FOR` → Organization (employer)
- `COMMUNICATES_WITH` → Person *(frequency: high/medium/low, last_contact: date)*
- `KNOWLEDGEABLE_ABOUT` → Topic *(confidence: 0-1, based on response patterns)*
- `RESPONSIBLE_FOR` → Action Item
- `MADE_DECISION` → Decision
- `MENTIONS` → Person *(context: "seeking approval", "escalating to", etc.)*

**Example:**
```
(Sarah Johnson) -[KNOWLEDGEABLE_ABOUT {confidence: 0.9}]-> (Budget Approval Process)
(Sarah Johnson) -[COMMUNICATES_WITH {frequency: 45 emails/month}]-> (Mike Chen)
(Sarah Johnson) -[MADE_DECISION]-> (Decision: "Approved Q4 marketing spend")
```

---

## 2. **Email**

**Properties:** Subject, Body, Timestamp, Message-ID, Has_Attachments, Sentiment, Urgency

**Relationships:**
- `SENT_BY` → Person
- `SENT_TO` → Person *(role: to/cc/bcc)*
- `PART_OF` → Conversation
- `REPLIES_TO` → Email
- `FORWARDS` → Email
- `CONTAINS_ATTACHMENT` → Document
- `MENTIONS_TOPIC` → Topic *(relevance: 0-1)*
- `CREATES` → Action Item
- `REFERENCES` → Organization
- `DISCUSSES` → Decision

**Example:**
```
(Email#12345) -[SENT_BY]-> (John Smith)
(Email#12345) -[SENT_TO {role: "cc"}]-> (Sarah Johnson)
(Email#12345) -[REPLIES_TO]-> (Email#12340)
(Email#12345) -[MENTIONS_TOPIC {relevance: 0.85}]-> (Vendor Contract Renewal)
(Email#12345) -[CREATES]-> (Action: "Review vendor proposal by Friday")
```

---

## 3. **Conversation/Thread**

**Properties:** Thread-ID, Subject, Start_Date, End_Date, Status (active/resolved/dormant), Participant_Count, Email_Count

**Relationships:**
- `CONTAINS` → Email
- `INVOLVES` → Person *(role: initiator/active_participant/observer)*
- `ABOUT` → Topic *(primary/secondary)*
- `RELATES_TO` → Organization
- `RESULTED_IN` → Decision
- `RESULTED_IN` → Action Item
- `HAS_OPEN_QUESTION` → Question
- `SPAWNED_FROM` → Conversation *(when thread splits)*
- `REQUIRES_FOLLOWUP_FROM` → Person

**Example:**
```
(Thread: "Q1 Budget Review") -[INVOLVES {role: "initiator"}]-> (Sarah Johnson)
(Thread: "Q1 Budget Review") -[INVOLVES {role: "participant"}]-> (Mike Chen, Finance Director)
(Thread: "Q1 Budget Review") -[ABOUT {type: "primary"}]-> (Budget Planning)
(Thread: "Q1 Budget Review") -[RESULTED_IN]-> (Decision: "Reallocate $50K to marketing")
(Thread: "Q1 Budget Review") -[HAS_OPEN_QUESTION]-> (Question: "What's the ROI target?")
```

---

## 4. **Topic**

**Properties:** Name, Category, Mention_Frequency, Trending_Score, First_Mentioned, Last_Mentioned

**Relationships:**
- `DISCUSSED_IN` → Conversation
- `MENTIONED_IN` → Email
- `SUBTOPIC_OF` → Topic *(hierarchical)*
- `RELATED_TO` → Topic *(semantic similarity)*
- `REQUIRES_EXPERTISE_IN` → Topic *(dependency)*
- `ASSOCIATED_WITH` → Organization
- `EXPERT_IS` → Person *(based on participation and responses)*
- `HAS_DECISION_ABOUT` → Decision
- `TRENDING_IN` → Time Period

**Example:**
```
(Topic: "Website Redesign") -[SUBTOPIC_OF]-> (Topic: "Digital Transformation")
(Topic: "Website Redesign") -[RELATED_TO]-> (Topic: "Brand Refresh")
(Topic: "Website Redesign") -[ASSOCIATED_WITH]-> (Acme Design Agency)
(Topic: "Website Redesign") -[EXPERT_IS]-> (Lisa Park, Product Manager)
(Topic: "Website Redesign") -[DISCUSSED_IN]-> (15 conversations)
```

---

## 5. **Organization/Company**

**Properties:** Name, Type (client/vendor/partner/competitor/internal), Industry, Relationship_Status, Contract_Value

**Relationships:**
- `MENTIONED_IN` → Email
- `DISCUSSED_IN` → Conversation
- `HAS_CONTACT` → Person *(role: primary/secondary/technical/billing)*
- `PROVIDES` → Service/Product
- `PARTNER_ON` → Topic/Project
- `COMPETING_WITH` → Organization
- `HAS_CONTRACT_WITH` → (implicit: your organization)
- `RELATED_TO_TOPIC` → Topic
- `INVOLVED_IN_DECISION` → Decision

**Example:**
```
(Acme Design Agency) -[HAS_CONTACT {role: "primary"}]-> (Jennifer Lee)
(Acme Design Agency) -[PROVIDES]-> (Web Design Services)
(Acme Design Agency) -[PARTNER_ON]-> (Topic: "Website Redesign")
(Acme Design Agency) -[MENTIONED_IN]-> (47 emails)
(Acme Design Agency) -[DISCUSSED_IN]-> (12 conversations)
```

---

## 6. **Action Item**

**Properties:** Description, Status (pending/in-progress/completed/blocked), Priority, Due_Date, Created_Date

**Relationships:**
- `CREATED_IN` → Email/Conversation
- `ASSIGNED_TO` → Person
- `CREATED_BY` → Person
- `RELATES_TO` → Topic
- `INVOLVES` → Organization
- `DEPENDS_ON` → Action Item *(blocking relationships)*
- `COMPLETED_BY` → Person *(when status = completed)*
- `MENTIONED_IN` → Email *(follow-ups, status updates)*
- `BLOCKS` → Action Item

**Example:**
```
(Action: "Finalize vendor contract") -[CREATED_IN]-> (Email#12345)
(Action: "Finalize vendor contract") -[ASSIGNED_TO]-> (Mike Chen)
(Action: "Finalize vendor contract") -[RELATES_TO]-> (Topic: "Vendor Selection")
(Action: "Finalize vendor contract") -[DEPENDS_ON]-> (Action: "Legal review complete")
(Action: "Finalize vendor contract") -[INVOLVES]-> (GlobalTech Solutions)
```

---

## 7. **Decision**

**Properties:** Description, Decision_Date, Impact_Level (high/medium/low), Confidence, Rationale

**Relationships:**
- `MADE_IN` → Conversation/Email
- `MADE_BY` → Person *(can be multiple people)*
- `AFFECTS` → Topic
- `INVOLVES` → Organization
- `LEADS_TO` → Action Item
- `SUPERSEDES` → Decision *(when reversed/updated)*
- `BASED_ON` → Information/Analysis *(referenced in emails)*
- `REQUIRES_APPROVAL_FROM` → Person
- `COMMUNICATED_TO` → Person

**Example:**
```
(Decision: "Switch to Vendor B") -[MADE_IN]-> (Thread: "Vendor Selection")
(Decision: "Switch to Vendor B") -[MADE_BY]-> (Sarah Johnson, Director)
(Decision: "Switch to Vendor B") -[AFFECTS]-> (Topic: "Cloud Infrastructure")
(Decision: "Switch to Vendor B") -[INVOLVES]-> (Vendor B Corp)
(Decision: "Switch to Vendor B") -[LEADS_TO]-> (Action: "Negotiate contract terms")
(Decision: "Switch to Vendor B") -[SUPERSEDES]-> (Decision: "Continue with Vendor A")
```

---

## 8. **Document/Attachment**

**Properties:** Filename, File_Type, Size, Version, Upload_Date, Content_Summary

**Relationships:**
- `ATTACHED_TO` → Email
- `SHARED_IN` → Conversation
- `SHARED_BY` → Person
- `RELATES_TO` → Topic
- `VERSION_OF` → Document *(version history)*
- `REFERENCED_IN` → Email *(mentioned but not attached)*
- `SUPPORTS` → Decision *(evidence/documentation)*
- `PROVIDED_BY` → Organization
- `DESCRIBES` → Product/Service

**Example:**
```
(Document: "Q4_Budget_Proposal_v3.xlsx") -[ATTACHED_TO]-> (Email#12350)
(Document: "Q4_Budget_Proposal_v3.xlsx") -[SHARED_BY]-> (Sarah Johnson)
(Document: "Q4_Budget_Proposal_v3.xlsx") -[RELATES_TO]-> (Topic: "Budget Planning")
(Document: "Q4_Budget_Proposal_v3.xlsx") -[VERSION_OF]-> (Document: "Q4_Budget_Proposal_v2.xlsx")
(Document: "Q4_Budget_Proposal_v3.xlsx") -[SUPPORTS]-> (Decision: "Approve Q4 budget")
```

---

## 9. **Question**

**Properties:** Question_Text, Asked_Date, Status (answered/unanswered/partially_answered), Urgency

**Relationships:**
- `ASKED_IN` → Email/Conversation
- `ASKED_BY` → Person
- `DIRECTED_TO` → Person *(explicitly or implicitly)*
- `ABOUT` → Topic
- `ANSWERED_BY` → Person
- `ANSWERED_IN` → Email
- `RELATED_TO` → Question *(similar questions)*
- `LEADS_TO` → Action Item *(when answer requires work)*
- `BLOCKS` → Decision *(unanswered question blocking progress)*

**Example:**
```
(Question: "What's our budget for this quarter?") -[ASKED_IN]-> (Email#12355)
(Question: "What's our budget for this quarter?") -[ASKED_BY]-> (Tom Wilson)
(Question: "What's our budget for this quarter?") -[DIRECTED_TO]-> (Sarah Johnson)
(Question: "What's our budget for this quarter?") -[ABOUT]-> (Topic: "Budget Planning")
(Question: "What's our budget for this quarter?") -[ANSWERED_BY]-> (Sarah Johnson)
(Question: "What's our budget for this quarter?") -[ANSWERED_IN]-> (Email#12358)
```

---

## 10. **Time Period**

**Properties:** Period_Type (day/week/month/quarter/year), Start_Date, End_Date, Fiscal_Period

**Relationships:**
- `CONTAINS` → Email
- `CONTAINS` → Conversation
- `CONTAINS` → Decision
- `DEADLINE_FOR` → Action Item
- `TOPIC_TRENDING_IN` → Topic *(what was hot in this period)*
- `HIGH_ACTIVITY_FROM` → Person *(who was most active)*
- `PRECEDED_BY` → Time Period
- `FOLLOWED_BY` → Time Period

**Example:**
```
(Period: "Q4 2025") -[CONTAINS]-> (523 emails)
(Period: "Q4 2025") -[CONTAINS]-> (87 conversations)
(Period: "Q4 2025") -[DEADLINE_FOR]-> (Action: "Complete annual review")
(Period: "Q4 2025") -[TOPIC_TRENDING_IN]-> (Topic: "Year-end planning")
(Period: "Q4 2025") -[HIGH_ACTIVITY_FROM]-> (Sarah Johnson, 156 emails sent)
```

---

## Putting It All Together - Example Query Path

**Question:** "What decisions were made about vendor selection in Q4, who was involved, and what actions came out of it?"

**Graph Traversal:**
```
(Period: "Q4 2025") -[CONTAINS]-> (Conversation: "Vendor Selection Discussion")
    -[ABOUT]-> (Topic: "Vendor Selection")
    -[INVOLVES]-> (Person: Sarah Johnson, Mike Chen, Lisa Park)
    -[INVOLVES]-> (Organization: Vendor B Corp)
    -[RESULTED_IN]-> (Decision: "Switch to Vendor B")
        -[MADE_BY]-> (Person: Sarah Johnson)
        -[LEADS_TO]-> (Action: "Negotiate contract by Dec 15")
            -[ASSIGNED_TO]-> (Person: Mike Chen)
            -[DEPENDS_ON]-> (Action: "Legal review complete")
```

This universal structure allows anyone—marketing, finance, engineering, HR, executives—to navigate email knowledge relevant to their work!