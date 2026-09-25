You are the lead software architect, ML engineer, AI engineer, backend engineer, frontend engineer, QA engineer, and research-paper implementation assistant for my final-year Phase-I project.

IMPORTANT:
DO NOT replace my existing project with a completely new project.

The project must remain a CONTINUATION and enhancement of the original research project:

"An AI-Powered Agricultural Decision Intelligence System for Precision Farming"

The newer HarvestIQ PRD represents UPDATES AND EXTENSIONS to the same project. It is NOT a replacement project.

Your responsibility is to analyze everything I already have, understand the existing implementation, preserve working functionality, fix architectural/security/data issues, implement the missing functionality required by the updated PRD, and bring the project to a complete, demonstrable, research-paper-ready state.

==================================================
1. SOURCE OF TRUTH
==================================================

You must inspect and use these sources before making major changes:

1. Existing project source code
2. Existing database
3. Existing frontend
4. Existing backend
5. Existing ML model
6. Existing research paper:
   "An AI-Powered Agricultural Decision Intelligence System for Precision Farming"
7. Existing First Review PPT
8. Updated HarvestIQ PRD
9. Review Circular / Second Review requirements

Preserve the terminology, project identity, research direction, and continuity of these materials.

Do not silently replace concepts.

When sources disagree:
- Preserve the original project identity.
- Treat the HarvestIQ PRD as an extension/update.
- Prefer actual implemented code over assumptions about implementation.
- Never invent results, metrics, datasets, or completed modules.
- Clearly document anything that is still missing.

==================================================
2. CURRENT PROJECT BASELINE
==================================================

The current project is a local full-stack Smart Farm application.

Current architecture:

Frontend:
- Static HTML/CSS/JavaScript
- Bootstrap 5.3
- Chart.js
- Served using Python HTTP server
- Approximately one main SPA-style interface

Backend:
- FastAPI
- Python 3.10
- SQLAlchemy
- SQLite
- REST API architecture

Existing AI/ML:
- Plant disease classification
- MobileNetV2-based model
- Fine-tuned model
- 27+ disease classes
- Image upload + prediction
- Top-5 predictions
- Annotated image output
- Cure/recommendation steps

Existing services:
- Weather API integration
- 5-day weather forecast
- Climate engine
- ET0 calculation
- Fungal-risk rules
- Crop recommendation rules
- Watering recommendation
- Fertilizer recommendation
- Rule-based cure-step generation
- Gmail SMTP notifications
- OTP password reset

Existing application features:
- Authentication
- Crop sessions
- Animal sessions
- Cost/profit analytics
- Dashboard analytics
- Market intelligence
- Disease detection
- Weather
- Recommendations
- Daily logs
- User statistics
- Email alerts

Current high-level architecture:

Browser
→ Frontend
→ FastAPI
→ SQLite / ML model / Weather API / Email

Current known technical problems:

1. Authentication is insecure because X-User-Id is trusted directly.
2. Password hashing currently uses weak SHA-256 + hardcoded salt.
3. Hardcoded API secrets exist.
4. SQLite database path is relative to current working directory.
5. Legacy rows have NULL user_id.
6. Some "live" values are fake/random.
7. Market intelligence currently contains random data.
8. CORS configuration is insecure.
9. Deprecated FastAPI startup event is used.
10. Frontend hardcodes localhost backend URL in multiple places.
11. Requirements are not properly pinned.
12. No proper automated tests.
13. No proper README.
14. Duplicate/stale files exist.
15. Unused model copies exist.
16. Windows stderr workaround exists and should be reviewed.
17. Current architecture is functional but not yet research-paper quality.

IMPORTANT:
Do not delete working functionality just to simplify the codebase.

==================================================
3. PRIMARY OBJECTIVE
==================================================

Transform the existing project into a COMPLETE:

AI-Powered Agricultural Decision Intelligence System for Precision Farming

while incorporating the HarvestIQ continuity features.

The final system should conceptually integrate:

A. Precision Agriculture Intelligence
- Crop recommendation
- Yield prediction
- Plant disease detection
- Weather-aware advisory
- Watering recommendations
- Fertilizer/resource recommendations
- Farm analytics
- Risk analysis

B. Conversational Agricultural Intelligence
- Natural-language farmer interaction
- Agricultural question answering
- Personalized agricultural advisory

C. Government Agricultural Knowledge Intelligence
- Government scheme discovery
- Scheme eligibility information
- Agricultural loans
- Kisan Credit Card information
- Crop insurance information
- Subsidies
- Government agricultural guidelines
- Required documents
- Application guidance
- Source citations

D. RAG-based Knowledge Retrieval
- Official document ingestion
- Text extraction
- Cleaning
- Semantic chunking
- Embedding generation
- Vector storage
- Similarity retrieval
- Context construction
- LLM response generation
- Citation/source traceability

E. Data-driven Farm Intelligence
- Historical farm information
- Weather data
- Crop information
- Market information
- Farm records
- Disease information
- User/farm profile

==================================================
4. DO NOT TURN THIS INTO A GOVERNMENT-SCHEME CHATBOT ONLY
==================================================

This is extremely important.

The final project must still clearly be a PRECISION FARMING / AGRICULTURAL DECISION INTELLIGENCE SYSTEM.

Government schemes, loans, insurance, and RAG are additional intelligence layers.

The conceptual evolution should be:

OLD:
AI-powered agricultural decision intelligence

UPDATED:
AI-powered agricultural decision intelligence
+
RAG-based agricultural knowledge
+
government agricultural services
+
conversational AI
+
personalized farmer assistance

==================================================
5. FIRST TASK — COMPLETE PROJECT AUDIT
==================================================

Before changing code, perform a complete repository audit.

Inspect:

- directory structure
- backend
- frontend
- database models
- API routes
- services
- ML model
- configuration
- environment variables
- dependencies
- frontend API calls
- authentication flow
- database relationships
- existing datasets
- unused files
- duplicate files
- logs
- documentation

Create:

PROJECT_AUDIT.md

Include:

1. Current architecture
2. Existing features
3. Existing APIs
4. Existing database tables
5. Existing models
6. Existing ML pipeline
7. Existing frontend modules
8. Working functionality
9. Broken functionality
10. Security risks
11. Data-quality issues
12. Missing PRD functionality
13. Missing research-paper functionality
14. Recommended implementation order

Do not modify code during the audit unless absolutely required to run the analysis.

==================================================
6. CREATE A FEATURE TRACEABILITY MATRIX
==================================================

Create:

FEATURE_TRACEABILITY.md

Map:

Original Project Requirement
→ Existing Implementation
→ HarvestIQ PRD Update
→ Required Enhancement
→ Implementation Status
→ Evidence Required for Research Paper

Example:

Crop Recommendation
→ Existing / Partial
→ Personalization enhancement
→ Improve recommendation logic
→ Status
→ Screenshot + model metrics

Government Scheme Retrieval
→ Missing
→ HarvestIQ requirement
→ Implement RAG
→ Status
→ Retrieval test + screenshots + citations

This matrix must cover the entire project.

==================================================
7. IMPLEMENTATION PRIORITY
==================================================

Work in this order:

PHASE 1 — Stabilize existing application

PHASE 2 — Security and architecture fixes

PHASE 3 — Improve existing AI/ML modules

PHASE 4 — Implement RAG knowledge system

PHASE 5 — Implement government scheme intelligence

PHASE 6 — Implement agricultural conversational assistant

PHASE 7 — Integrate personalized decision intelligence

PHASE 8 — Improve UI/UX

PHASE 9 — Testing and evaluation

PHASE 10 — Research documentation and evidence

Do not jump directly into UI redesign before backend architecture is stable.

==================================================
8. SECURITY FIXES
==================================================

Fix the existing security problems without breaking the existing application.

Implement:

- secure password hashing using bcrypt or another appropriate password hashing mechanism
- JWT/session-based authentication
- proper authentication middleware/dependencies
- authorization checks for user-owned resources
- stop blindly trusting X-User-Id
- secure environment variable handling
- remove hardcoded API credentials
- configure .env safely
- create .env.example
- secure CORS
- validate request payloads
- validate uploaded files
- restrict dangerous file types
- reasonable upload size limits
- protect sensitive API routes

IMPORTANT:

Never print or expose real API keys, passwords, tokens, or secrets in documentation.

Never hardcode secrets in source code.

==================================================
9. DATABASE IMPROVEMENTS
==================================================

Fix:

- relative SQLite database path
- user ownership
- NULL legacy user_id problem
- missing constraints where appropriate
- inconsistent relationships
- data validation
- migration handling

Do NOT destroy existing user/demo data.

Create safe migration logic.

Use an absolute database path derived from the project directory.

Document database schema.

Create:

DATABASE_SCHEMA.md

==================================================
10. CONFIGURATION IMPROVEMENT
==================================================

Create a centralized configuration system.

All environment-dependent settings must come from configuration:

- API URLs
- weather API keys
- LLM keys
- email credentials
- database path
- JWT secret
- model path
- vector database path
- application environment
- frontend/backend URLs

Frontend must not repeat:

http://localhost:8000

in dozens of locations.

Use one configurable API base URL.

==================================================
11. PRESERVE AND IMPROVE EXISTING AI MODULES
==================================================

Existing functionality must remain.

Improve each module rather than replacing it.

MODULE 1:
Crop Recommendation

Requirements:
- clear input schema
- preprocessing
- recommendation engine/model
- explanation
- validation
- confidence if available
- clean UI output

MODULE 2:
Yield Prediction

If not currently implemented, implement a proper research-oriented module.

Use an actual dataset.

Document:
- dataset
- features
- preprocessing
- model
- train/test split
- evaluation metrics
- prediction endpoint

Do NOT invent performance.

MODULE 3:
Plant Disease Detection

Preserve the existing MobileNetV2 implementation.

Improve:
- preprocessing validation
- confidence handling
- image validation
- top-k display
- useful explanation
- disease information
- cure/advisory information
- error handling

Use actual validation results.

MODULE 4:
Weather-aware Advisory

Preserve current weather integration.

Replace fake values with actual API-backed values where possible.

Do not claim weather data is real-time if the implementation does not actually provide it.

MODULE 5:
Watering Recommendation

Maintain current rule-based logic but clearly document that it is a decision-rule engine unless a learned model is actually implemented.

MODULE 6:
Fertilizer / Resource Recommendation

Improve this module and document its methodology honestly.

MODULE 7:
Farm Analytics

Preserve:
- cost
- revenue
- profit
- crop tracking
- animal tracking
- daily logging

Do not remove animal management if it already exists.

==================================================
12. MARKET INTELLIGENCE
==================================================

The current market intelligence contains random/generated values.

Do NOT leave random values labeled as live market intelligence.

Choose one of these approaches:

Preferred:
Replace with a genuine data source/API if technically and legally appropriate.

Otherwise:
Clearly label the feature as:
"Demonstration / Simulated Market Data"

and isolate the simulation logic.

Never present synthetic values as real-world market data.

Document the source.

==================================================
13. RAG KNOWLEDGE BASE
==================================================

Implement a production-style local RAG pipeline.

Pipeline:

Official Documents
→ Text Extraction
→ Cleaning
→ Metadata Extraction
→ Semantic Chunking
→ Embeddings
→ Vector Database
→ Similarity Retrieval
→ Context Ranking
→ LLM
→ Grounded Answer
→ Citation

Use a maintainable design.

Possible technologies:
- FAISS
- ChromaDB
- sentence-transformers
- another appropriate embedding system
- LLM API/local model based on available environment

Do not assume a specific model without checking the current environment.

Create a clear abstraction so the LLM can be replaced later.

==================================================
14. KNOWLEDGE BASE CONTENT
==================================================

Create a structured knowledge ingestion framework.

Initial supported domains should include the PRD-defined agricultural information, such as:

- PM-KISAN
- Kisan Credit Card
- NABARD agricultural loan information
- PM Fasal Bima Yojana
- Agriculture Infrastructure Fund
- Soil Health Card
- PM Krishi Sinchai Yojana
- RKVY
- Ministry of Agriculture FAQs
- other official agricultural documents actually collected

Use official primary sources wherever possible.

Every document should have metadata such as:

- document title
- scheme name
- ministry/organization
- category
- eligibility
- benefits
- required documents
- publication/update date
- source URL
- document version if available

Do not fabricate government information.

==================================================
15. RAG QUALITY CONTROLS
==================================================

The RAG assistant must NOT simply generate free-form answers.

Implement:

- retrieval-first flow
- relevance threshold
- context limitation
- source attribution
- citation mapping
- "information not found" response
- prevention of unsupported claims
- clear distinction between retrieved facts and generated explanation

If the knowledge base does not contain sufficient information:

Respond with something like:

"I could not find sufficient information in the available official documents."

Do not hallucinate.

==================================================
16. AGRICULTURAL CONVERSATIONAL ASSISTANT
==================================================

Create a unified assistant that can understand queries such as:

- Which crops are suitable for my soil?
- What disease does this leaf have?
- How much should I water?
- What government schemes may apply to me?
- What documents are required?
- What agricultural loans are available?
- Am I eligible for this scheme?
- What crop insurance information is available?
- What should I consider before planting?

The assistant should route queries to the appropriate module.

Suggested architecture:

User Query
→ Intent Detection / Router
→ Appropriate Tool/Module
→ ML / CV / Weather / RAG
→ Result
→ LLM explanation
→ Citation if knowledge-based
→ Final response

Do NOT let the LLM directly invent database/API/model results.

==================================================
17. FARMER PROFILE / PERSONALIZATION
==================================================

Add a structured farmer/farm profile where practical.

Potential fields:

- location
- land area
- soil information
- crop history
- irrigation availability
- cultivation preferences
- livestock information
- resource constraints

Use this information to personalize recommendations.

Do not infer sensitive information.

==================================================
18. SYSTEM ARCHITECTURE
==================================================

Create a documented architecture containing:

1. Presentation layer
2. API layer
3. Authentication layer
4. Intelligence layer
5. ML/CV models
6. RAG pipeline
7. Vector database
8. Knowledge base
9. Weather/API integration
10. Database
11. Notification subsystem

Create:

ARCHITECTURE.md

Include:
- component diagram
- data flow
- request flow
- RAG flow
- authentication flow
- module interaction

Also generate a clean architecture diagram suitable for:

- research paper
- PPT
- project documentation

==================================================
19. API DOCUMENTATION
==================================================

Document all APIs.

Create:

API_DOCUMENTATION.md

For each endpoint include:

- method
- path
- authentication requirement
- request
- response
- errors
- example

Ensure FastAPI /docs is clean and meaningful.

==================================================
20. FRONTEND IMPROVEMENT
==================================================

Do not completely redesign the application unless required.

Improve the existing interface while maintaining the current workflow.

Provide clear sections/dashboard cards for:

- Farm Overview
- Crop Recommendation
- Yield Prediction
- Disease Detection
- Weather
- Watering
- Fertilizer/Resources
- Market Intelligence
- Government Schemes
- Agricultural Loans
- AI Assistant
- Farm Analytics

The UI must communicate that these are components of ONE Agricultural Decision Intelligence System.

Use professional research-project quality UI.

Do not add decorative UI that creates unnecessary complexity.

==================================================
21. TESTING
==================================================

Create a proper testing structure.

Backend:
- unit tests
- API tests
- authentication tests
- authorization tests
- database tests
- ML endpoint tests
- RAG tests

Frontend:
- essential integration checks

Security:
- unauthorized access
- IDOR/user isolation
- invalid token
- invalid file upload
- malformed input

RAG:
- retrieval relevance
- citation presence
- unsupported questions
- no-document scenario
- hallucination resistance

Create:

TEST_PLAN.md

and generate test results.

==================================================
22. RESEARCH EVALUATION
==================================================

This is critical because this is also a research project.

For every ML module, collect actual evaluation metrics.

Examples:

Classification:
- Accuracy
- Precision
- Recall
- F1-score
- Confusion matrix

Regression:
- MAE
- RMSE
- R²

RAG:
- retrieval precision / hit rate where measurable
- answer correctness
- citation correctness
- groundedness
- response latency

System:
- API response time
- RAG response time
- model inference time
- resource usage

Do NOT create fake values.

If a metric cannot currently be measured, mark it:

[METRIC TO BE MEASURED]

==================================================
23. EXPERIMENTAL DATA
==================================================

For every experiment document:

- dataset name
- source
- dataset size
- features
- classes
- preprocessing
- train/validation/test split
- model
- hyperparameters
- training procedure
- evaluation metrics
- results
- limitations

If the project currently lacks a dataset for a module:

Do not pretend one exists.

Identify the missing dataset and propose an appropriate source.

==================================================
24. RESEARCH PAPER REQUIREMENTS
==================================================

The final project must support the Second Review research paper.

The paper should retain the original title:

"An AI-Powered Agricultural Decision Intelligence System for Precision Farming"

Paper structure:

1. Title
2. Abstract
3. Keywords
4. Introduction
5. Problem Statement
6. Background and Motivation
7. Research Objectives
8. Literature Survey / Related Work
9. Research Gap
10. Proposed Methodology
11. System Architecture
12. Module Description
13. Algorithms and Techniques
14. Dataset and Data Sources
15. RAG Knowledge Base
16. Implementation
17. Experimental Setup
18. Results and Discussion
19. Comparative Analysis
20. Advantages
21. Limitations
22. Future Enhancements
23. Conclusion
24. References

Do not claim modules are implemented unless verified from the repository.

Separate:

Implemented
Partially Implemented
Planned

==================================================
25. LITERATURE REVIEW
==================================================

The existing paper already contains a literature survey.

DO NOT unnecessarily throw it away.

Instead:

- preserve relevant papers
- update where necessary
- ensure approximately 20–25 strong papers as required by the review
- organize them thematically
- identify research gaps
- connect literature gaps directly to implemented system modules

Themes can include:

- crop recommendation
- yield prediction
- disease detection
- precision agriculture
- explainable AI
- agricultural decision support
- LLMs
- RAG
- agricultural conversational systems

Use real papers and real citations.

==================================================
26. SECOND REVIEW EVIDENCE
==================================================

Generate a directory:

research_evidence/

Store:

- architecture diagram
- screenshots
- API test screenshots
- model results
- confusion matrices
- charts
- dataset statistics
- RAG retrieval examples
- citation examples
- performance measurements
- comparison tables

Each screenshot should have a meaningful filename.

Example:

01_dashboard.png
02_crop_recommendation.png
03_disease_detection.png
04_weather_advisory.png
05_rag_scheme_query.png
06_scheme_citation.png

==================================================
27. RESEARCH PAPER DATA PACKAGE
==================================================

Create:

research_paper_data/

Include:

project_summary.md
datasets.md
models.md
experiments.md
metrics.md
results.md
architecture.md
limitations.md
future_work.md
references.md

The objective is that the paper can be written directly from this package.

==================================================
28. README
==================================================

Create a professional README.md containing:

Project title
Problem
Objectives
Features
Architecture
Technology stack
Modules
AI/ML components
RAG pipeline
Setup
Environment variables
Database
Running instructions
API documentation
Testing
Research methodology
Results
Limitations
Future work

Do not put real credentials in README.

==================================================
29. DEPENDENCY MANAGEMENT
==================================================

Clean and pin dependencies.

Create/update:

requirements.txt

Document:

- Python version
- required packages
- model dependencies
- system dependencies

Remove unused dependencies when safe.

==================================================
30. REPOSITORY CLEANUP
==================================================

Identify and safely handle:

- unused model copies
- backup HTML files
- temporary scripts
- logs
- old artifacts
- generated files
- unnecessary cache folders

DO NOT delete anything until confirming that it is unused.

==================================================
31. ERROR HANDLING
==================================================

Improve:

- backend exceptions
- validation
- API errors
- frontend errors
- model errors
- API failures
- missing data
- RAG failures
- invalid images
- authentication failures

Errors should be user-friendly and developer-debuggable.

==================================================
32. OBSERVABILITY
==================================================

Add appropriate logging.

Log:

- API request failures
- ML inference failures
- RAG retrieval failures
- external API failures
- authentication failures

Never log:
- passwords
- API keys
- JWT tokens
- sensitive credentials

==================================================
33. PERFORMANCE
==================================================

Measure rather than guess.

Optimize:

- model loading
- API response time
- vector retrieval
- database queries
- frontend repeated API calls
- unnecessary model initialization

If below-5-second response time is a project requirement, measure it.

Do not claim compliance without measurement.

==================================================
34. FINAL USER FLOW
==================================================

The final system should support a logical user journey such as:

User Login
→ Farmer/Farm Profile
→ Dashboard
→ Enter Farm Information
→ Crop Recommendation
→ Yield Prediction
→ Weather Analysis
→ Watering/Fertilizer Recommendation
→ Upload Plant Image
→ Disease Detection
→ Ask AI Assistant
→ Retrieve relevant agricultural information
→ Government Scheme / Loan / Insurance information
→ Display source citation
→ Save relevant farm activity
→ View analytics

==================================================
35. IMPORTANT CONTINUITY RULE
==================================================

Do not rename the entire project to HarvestIQ.

HarvestIQ should be treated as an internal product/updated feature direction if useful.

The academic research identity remains:

"An AI-Powered Agricultural Decision Intelligence System for Precision Farming"

The project evolution is:

Version 1:
AI-powered precision farming decision support

Version 2:
Integrated agricultural intelligence + AI advisory

Updated Version:
Integrated agricultural intelligence
+
RAG
+
government agricultural knowledge
+
conversational assistant
+
personalized farmer decision support

==================================================
36. NO FAKE IMPLEMENTATION
==================================================

This rule is mandatory.

Never:

- fabricate model accuracy
- fabricate dataset size
- fabricate users
- fabricate API data
- fabricate market prices
- fabricate RAG evaluation
- fabricate screenshots
- fabricate experiments
- claim an API is live if it is not
- claim government information is verified unless sourced
- claim a model is trained if it is not
- claim a module is implemented if it is only planned

When something is missing:

Clearly report:

MISSING:
REQUIRED:
RECOMMENDED IMPLEMENTATION:
EVIDENCE NEEDED:

==================================================
37. DEVELOPMENT METHOD
==================================================

Do not make huge uncontrolled changes.

For every major phase:

1. Inspect
2. Plan
3. Implement
4. Run
5. Test
6. Verify existing functionality
7. Document
8. Move to next phase

After every major change:

- run backend
- verify APIs
- run tests
- verify frontend
- check logs
- ensure no regression

==================================================
38. GIT / CHANGE SAFETY
==================================================

Before major changes:

Create a clear checkpoint/commit.

Use meaningful commit messages.

Do not overwrite or delete the existing project without a recoverable state.

==================================================
39. FINAL DELIVERABLES
==================================================

At the end, the repository should contain:

/backend
/frontend
/tests
/docs
/research_evidence
/research_paper_data

and:

README.md
PROJECT_AUDIT.md
FEATURE_TRACEABILITY.md
ARCHITECTURE.md
DATABASE_SCHEMA.md
API_DOCUMENTATION.md
TEST_PLAN.md
requirements.txt
.env.example

plus all required source/documentation files.

==================================================
40. FINAL REPORT
==================================================

At the end of the entire process, create:

FINAL_PROJECT_REPORT.md

It must contain:

1. Executive summary
2. Before vs After
3. Existing features preserved
4. New features implemented
5. Bugs fixed
6. Security improvements
7. Architecture changes
8. AI/ML modules
9. RAG implementation
10. Knowledge base
11. Dataset information
12. Experimental results
13. Performance results
14. Testing results
15. Remaining limitations
16. Future enhancements
17. Research-paper readiness
18. Second Review readiness
19. Exact things still requiring my input

==================================================
41. HOW TO WORK WITH ME
==================================================

Do NOT ask me 20 questions at the beginning.

First inspect the repository and all available documents.

Then give me:

A. Current-state summary
B. Missing-feature summary
C. Implementation plan
D. Files that will be modified
E. Risks
F. Information that genuinely cannot be determined from the repository

Then begin implementation.

Only ask me for information when it is truly impossible to determine from the project.

==================================================
42. FINAL SUCCESS CRITERIA
==================================================

The project is considered complete only when:

[ ] Existing Smart Farm functionality works
[ ] Authentication is secure
[ ] User data isolation works
[ ] Database works reliably
[ ] Existing ML model works
[ ] Crop recommendation works
[ ] Yield prediction is implemented or clearly documented as pending
[ ] Disease detection works
[ ] Weather integration works
[ ] Water/fertilizer recommendations work
[ ] Market data is not falsely represented as live
[ ] RAG pipeline works
[ ] Government knowledge base works
[ ] Scheme retrieval works
[ ] Loan/insurance information retrieval works
[ ] Citations work
[ ] Conversational assistant works
[ ] Personalized recommendations work
[ ] APIs are documented
[ ] Tests exist
[ ] Security issues are addressed
[ ] Documentation is complete
[ ] Research evidence is collected
[ ] Actual metrics are measured
[ ] Research paper sections are supported by implementation evidence
[ ] Project architecture matches the academic description
[ ] Second Review requirements are covered

==================================================
43. FIRST RESPONSE FORMAT
==================================================

Before editing anything, respond with exactly these sections:

# 1. CURRENT PROJECT UNDERSTANDING
# 2. EXISTING FEATURES
# 3. EXISTING RESEARCH PAPER COVERAGE
# 4. HARVESTIQ CONTINUITY FEATURES
# 5. MISSING IMPLEMENTATION
# 6. SECURITY / TECHNICAL ISSUES
# 7. SECOND REVIEW GAPS
# 8. IMPLEMENTATION ROADMAP
# 9. FILES TO BE CREATED
# 10. INFORMATION STILL REQUIRED FROM ME

Then wait for my confirmation before performing destructive or major architectural changes.