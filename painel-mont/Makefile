.PHONY: setup seed api front test check

setup:            ## instala backend e frontend
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

seed:             ## migra e carrega os dados de demonstração
	cd backend && python manage.py migrate && python manage.py seed_demo --reset

api:              ## sobe a API analítica em :8000
	cd backend && python -m uvicorn api.main:app --reload --port 8000

front:            ## sobe o painel em :5173
	cd frontend && npm run dev

test:             ## roda a suíte de testes do backend
	cd backend && python -m pytest

check:            ## testes + typecheck do front
	cd backend && python -m pytest
	cd frontend && npm run typecheck
