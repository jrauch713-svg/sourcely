# Sourcely (working name)

Entry-tier CRM for solo interior designers — proposals, product sourcing, and procurement in one place.

## Stack

**FastAPI + SQLAlchemy async + PostgreSQL** (proven patterns from cipherform).  
SQLite in-memory for tests, PostgreSQL for prod.  
No ORM magic — explicit async SQL, minimal abstraction.

Why this stack over Next.js/Supabase:
- Same patterns as cipherform → fast execution, fewer surprises
- PostgreSQL gives us the relational model designers' data naturally fits
  (projects → clients → products → line items)
- No vendor lock-in; easy to self-host or deploy to any cloud
- FastAPI's async performance is more than enough for this use case

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your secrets
uvicorn app.main:app --reload
```

## Test

```bash
pytest tests/ -v
```

## Scope (this slice)

- [x] Project scaffold
- [ ] Auth: register/login/JWT (designer accounts only)
- [ ] Core data model: Designer, Project, Client
- [ ] TDD throughout

## Future slices (not built yet)

- Product library per project
- Proposal generation
- Per-line-item client approval
- Stripe invoicing
- Project templates
- Landing page + Google Ads validation
