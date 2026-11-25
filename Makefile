# Comandi rapidi per lo stack music_stack.
# Nota: il codice e il deploy vivono entrambi in /opt/slskd-fy.

COMPOSE_FILE := deploy/docker-compose.yml
# Su questa LXC l'utente non e' nel gruppo docker: serve sudo.
# Se hai accesso diretto al socket, sovrascrivi con: make DOCKER="docker"
DOCKER  ?= sudo docker
COMPOSE := $(DOCKER) compose -f $(COMPOSE_FILE)

.DEFAULT_GOAL := help
.PHONY: help up up-no-build down stop start restart build pull ps logs logs-app logs-slskd validate dry-run shell health

help:
	@echo "Comandi disponibili (stack music_stack):"
	@echo "  make up           Avvia/aggiorna lo stack (build + detached)"
	@echo "  make up-no-build  Avvia senza ricostruire le immagini"
	@echo "  make down         Ferma e rimuove i container (dati in /mnt/music preservati)"
	@echo "  make stop         Ferma i container senza rimuoverli"
	@echo "  make start        Riavvia i container fermati"
	@echo "  make restart      Riavvia tutti i servizi"
	@echo "  make build        Ricostruisce le immagini"
	@echo "  make pull         Aggiorna le immagini dalle registry"
	@echo "  make ps           Mostra lo stato dei container"
	@echo "  make logs         Log di tutti i servizi (follow)"
	@echo "  make logs-app     Log di slskd-fy (follow)"
	@echo "  make logs-slskd   Log di slskd (follow)"
	@echo "  make validate     Verifica il compose senza avviare nulla"
	@echo "  make dry-run      Mostra cosa farebbe 'make up' senza applicarlo"
	@echo "  make shell        Shell interattiva dentro slskd-fy"
	@echo "  make health       Controlla gli endpoint HTTP di slskd-fy e slskd"

up:
	$(COMPOSE) up -d --build

up-no-build:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

stop:
	$(COMPOSE) stop

start:
	$(COMPOSE) start

restart:
	$(COMPOSE) restart

build:
	$(COMPOSE) build

pull:
	$(COMPOSE) pull

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

logs-app:
	$(COMPOSE) logs -f --tail=100 slskd-fy

logs-slskd:
	$(COMPOSE) logs -f --tail=100 slskd

validate:
	$(COMPOSE) config --quiet && echo "Compose valido"

dry-run:
	$(COMPOSE) up -d --dry-run

shell:
	$(COMPOSE) exec slskd-fy /bin/bash

health:
	@curl -fsS http://localhost:8000/health && echo " -> slskd-fy OK"
	@curl -fsS http://localhost:5030/health && echo " -> slskd OK"
