# Engineering Certification Enablement Guide (Synthetic)

> **Disclaimer**: This document is synthetic data created for demonstration purposes only.
> All identifiers are fabricated. Do not use real employee data.

---

## Role-to-Certification Mapping

### Cloud Engineer
- **Primary**: AZ-204 (Developing Solutions for Microsoft Azure)
- **Secondary**: AZ-305 (Designing Microsoft Azure Infrastructure Solutions)
- **Recommended study pattern**: 1–2 hours daily focused study; weekly assessment checkpoints
- **Target practice score before exam**: 75%+

### DevOps Engineer
- **Primary**: AZ-400 (Designing and Implementing Microsoft DevOps Solutions)
- **Secondary**: AZ-104 (Microsoft Azure Administrator)
- **Recommended study pattern**: Focus on hands-on pipeline labs; 25+ hours total
- **Target practice score before exam**: 75%+

### Data Engineer
- **Primary**: DP-203 (Data Engineering on Microsoft Azure)
- **Secondary**: DP-900 (Azure Data Fundamentals) as pre-req for beginners
- **Recommended study pattern**: Emphasis on Synapse Analytics and Data Factory
- **Target practice score before exam**: 75%+

### Cloud Architect
- **Primary**: AZ-305 (Designing Microsoft Azure Infrastructure Solutions)
- **Secondary**: AZ-700 (Azure Network Engineer Associate)
- **Prerequisite**: AZ-104 strongly recommended before AZ-305
- **Recommended study pattern**: Architecture case-study reviews; 30+ hours total

---

## Study Effectiveness Patterns (from synthetic cohort data)

Learners who passed their certifications showed consistent patterns:

1. **Hours**: More than 20 hours of focused study (not just scheduled time)
2. **Practice scores**: Consistently above 75% in practice assessments before exam day
3. **Work schedule**: Fewer than 20 meeting hours per week correlated with higher pass rates
4. **Spacing**: Study distributed across 4–8 weeks outperforms cramming
5. **Weak areas**: Explicitly targeting identified weak domains in the final 2 weeks

Learners at risk of failure typically show:
- Practice scores below 65% in the week before the exam
- High meeting load (>25 hours/week) with no schedule accommodation
- Actual study hours below 60% of planned hours (engagement gap)
- No mock exam completed before exam day

---

## AZ-204: Key Topics by Domain

### Domain 1: Develop Azure compute solutions (25% of exam)
- **Azure Functions**: triggers, bindings, durable functions, deployment slots
- **Azure App Service**: scaling, slots, deployment, custom domains, authentication
- **Azure Container Instances and Apps**: container deployment, revision management

### Domain 2: Develop for Azure storage (15% of exam)
- **Blob Storage**: lifecycle management, access tiers, SAS tokens, metadata
- **Cosmos DB**: consistency models, partition keys, indexing, change feed
- **Table Storage**: entity design, query patterns
- **Queue Storage**: visibility timeout, poison messages

### Domain 3: Implement Azure security (20% of exam)
- **Key Vault**: secrets, certificates, keys; managed HSM
- **Managed Identity**: system-assigned vs user-assigned; RBAC
- **App configuration**: feature flags, dynamic configuration

### Domain 4: Monitor, troubleshoot, optimize (15% of exam)
- **Application Insights**: distributed tracing, custom metrics, sampling
- **Azure Monitor**: alerts, action groups, workbooks
- **Cache for Redis**: eviction policies, session state, data structures

### Domain 5: Connect to and consume Azure services (25% of exam)
- **API Management**: policies, subscriptions, products, versioning
- **Event Grid**: event routing, filtering, dead-lettering
- **Service Bus**: queues vs topics, sessions, transactions
- **Event Hub**: partitions, consumer groups, capture

---

## AZ-400: Key Topics by Domain

### Domain 3: Build and release pipelines (40% of exam — highest weight)
- **Azure Pipelines**: YAML pipelines, templates, multi-stage
- **GitHub Actions**: workflows, reusable workflows, environments
- **Deployment strategies**: blue-green, canary, rolling, feature flags
- **Azure Artifacts**: feeds, upstream sources, versioning

### Domain 4: Security and compliance (20% of exam)
- **Dependency scanning**: Dependabot, OWASP dependency check
- **Secret management**: Azure Key Vault integration, variable groups
- **SAST/DAST**: integration into pipelines

---

## DP-203: Key Topics by Domain

### Domain 1: Data storage design (40% — highest weight)
- **Azure Data Lake Storage Gen2**: hierarchical namespace, ACLs, performance tiers
- **Synapse Analytics**: dedicated vs serverless SQL pools, Spark pools
- **Delta Lake**: ACID transactions, schema evolution, time travel
- **Azure SQL Database**: elastic pools, geo-replication, Always Encrypted

### Domain 2: Data processing (25% of exam)
- **Azure Data Factory**: linked services, integration runtime, data flows
- **Azure Databricks**: cluster types, Delta Live Tables, Unity Catalog
- **Stream Analytics**: windowing functions, reference data, output sinks

---

## Study Schedule Template

| Week | Focus | Hours | Checkpoint |
|------|-------|-------|------------|
| 1 | Fundamentals review + Domain 1 | 4–5h | Self-assessment quiz |
| 2 | Domain 2 + Domain 3 | 4–5h | Practice questions D2+D3 |
| 3 | Domain 4 + Domain 5 | 4–5h | Practice questions D4+D5 |
| 4 | Full mock exam + weak area review | 5–6h | Mock exam ≥ 70% target |
| 5 | Targeted weak area review | 3–4h | Second mock exam |
| 6 | Final review + exam-day prep | 2–3h | Readiness check |

---

*This document is synthetic and was generated for demonstration purposes. Exam domain weights and
 passing scores are based on publicly available Microsoft certification pages.*
