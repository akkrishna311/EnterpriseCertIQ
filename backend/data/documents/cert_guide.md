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

### AI Engineer
- **Primary**: AI-102 (Azure AI Engineer Associate)
- **Prerequisite**: AI-900 (Azure AI Fundamentals) recommended for beginners
- **Recommended study pattern**: Hands-on with Azure AI services + Azure OpenAI; 25+ hours total
- **Target practice score before exam**: 75%+

### Data Scientist
- **Primary**: DP-100 (Azure Data Scientist Associate)
- **Secondary**: DP-203 (Data Engineering on Microsoft Azure) for data-platform depth
- **Recommended study pattern**: Azure ML SDK labs, AutoML, and MLflow tracking; 25+ hours total
- **Target practice score before exam**: 75%+

### AI Practitioner
- **Primary**: AI-900 (Azure AI Fundamentals)
- **Recommended study pattern**: Concept-focused; 10–12 hours total; good entry certification
- **Target practice score before exam**: 75%+

### Security Architect
- **Primary**: SC-100 (Microsoft Cybersecurity Architect Expert)
- **Prerequisite**: SC-200/SC-300/AZ-500 strongly recommended before SC-100
- **Recommended study pattern**: Zero Trust case studies; 30+ hours total

### Microsoft 365 Administrator
- **Primary**: MS-102 (Microsoft 365 Administrator Expert)
- **Recommended study pattern**: Tenant + identity + Defender + Purview labs; 28+ hours total
- **Target practice score before exam**: 75%+

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

## AI-102: Key Topics by Domain

### Domain 1: Plan and manage an Azure AI solution (20% of exam)
- **Azure AI services**: multi-service vs single-service resources, keys and endpoints
- **Responsible AI**: content moderation, transparency notes, fairness considerations
- **Containers**: deploy Cognitive Services in containers, disconnected billing
- **Security**: managed identity, private endpoints, key rotation

### Domain 2: Implement generative AI solutions (15% of exam)
- **Azure OpenAI**: deployments, completions vs chat, function calling
- **Prompt engineering**: system messages, few-shot, temperature/top-p tuning
- **Retrieval Augmented Generation (RAG)**: grounding with Azure AI Search, citations

### Domain 3: Implement computer vision solutions (20% of exam)
- **Azure AI Vision**: image analysis, OCR/Read, spatial analysis
- **Custom Vision**: classification vs object detection, training/publishing
- **Face API**: detection, recognition, responsible-use gating

### Domain 4: Implement natural language processing solutions (20% of exam)
- **Azure AI Language**: entity recognition, sentiment, key phrases, PII detection
- **Conversational language understanding**: intents, entities, orchestration
- **Speech**: speech-to-text, text-to-speech, custom speech, translation

### Domain 5: Implement knowledge mining and document intelligence (25% — highest weight)
- **Azure AI Search**: indexers, skillsets, knowledge store, semantic ranking
- **Document Intelligence**: prebuilt vs custom models, composed models

---

## DP-100: Key Topics by Domain

### Domain 1: Design and prepare a machine learning solution (25% of exam)
- **Azure ML workspace**: compute targets, datastores, data assets, environments
- **Compute**: compute instances vs clusters, scaling, idle shutdown

### Domain 2: Explore data and train models (35% — highest weight)
- **Automated ML**: task types, featurization, primary metrics
- **MLflow**: experiment tracking, autologging, model registry
- **Hyperparameter tuning**: sweep jobs, sampling, early termination policies

### Domain 3: Prepare a model for deployment (20% of exam)
- **Pipelines**: components, reusable steps, scheduling
- **Environments**: curated vs custom, conda/docker specifications

### Domain 4: Deploy and retrain a model (20% of exam)
- **Online endpoints**: managed vs Kubernetes, blue-green deployment, traffic split
- **Batch endpoints**: scoring pipelines, parallelism
- **Monitoring**: data drift, the Responsible AI dashboard

---

## AI-900: Key Topics by Domain

### Domain 1: AI workloads and considerations (20% of exam)
- **Responsible AI principles**: fairness, reliability, privacy, inclusiveness, transparency, accountability
- **Common workloads**: prediction, anomaly detection, computer vision, NLP, generative AI

### Domain 2: Machine learning fundamentals (25% — highest weight)
- **Model types**: regression, classification, clustering
- **Azure Machine Learning**: AutoML, designer, evaluation metrics

### Domain 3: Computer vision workloads (20% of exam)
- **Azure AI Vision**: image classification, object detection, OCR, faces

### Domain 4: Natural language processing workloads (20% of exam)
- **Azure AI Language and Speech**: key phrases, sentiment, translation, speech

### Domain 5: Generative AI workloads (15% of exam)
- **Azure OpenAI and Copilot**: foundation models, prompts, responsible use

---

## SC-100: Key Topics by Domain

### Domain 1: Design a Zero Trust strategy and architecture (30% — highest weight)
- **Zero Trust**: verify explicitly, least privilege, assume breach
- **Identity**: Conditional Access, PIM, identity protection with Microsoft Entra
- **Microsoft Defender**: XDR strategy across identity, endpoint, email, cloud apps

### Domain 2: Evaluate GRC strategies and security operations (25% of exam)
- **Compliance**: Microsoft Purview, regulatory frameworks, Defender for Cloud regulatory compliance
- **Security operations**: Microsoft Sentinel, SIEM/SOAR, incident response design

### Domain 3: Design security for infrastructure (25% of exam)
- **Endpoints, networks, compute**: segmentation, private access, hardening baselines
- **Defender for Cloud**: secure score, workload protection

### Domain 4: Design a strategy for data and applications (20% of exam)
- **Data security**: classification, encryption, DLP strategy
- **Application security**: DevSecOps, secret management, API protection

---

## MS-102: Key Topics by Domain

### Domain 1: Deploy and manage a Microsoft 365 tenant (25% of exam)
- **Tenant**: domains, organizational settings, admin roles, service health

### Domain 2: Implement and manage identity and access (25% of exam)
- **Microsoft Entra ID**: users/groups, MFA, Conditional Access, self-service password reset
- **Hybrid identity**: Entra Connect, password hash sync, seamless SSO

### Domain 3: Manage security and threats using Microsoft 365 Defender (25% of exam)
- **Defender for Office 365**: Safe Attachments, Safe Links, anti-phishing policies
- **Defender for Endpoint and Cloud Apps**: threat policies, alerts, investigation

### Domain 4: Manage compliance using Microsoft Purview (25% of exam)
- **Data loss prevention (DLP)**: policies, sensitive info types
- **Information protection**: sensitivity labels, retention, eDiscovery

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
