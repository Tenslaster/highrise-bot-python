# SDK Python pour Highrise Bot

<p align="center">
  <strong>SDK Python non officiel et orienté production pour les bots Highrise</strong><br />
  Surface <code>BaseBot</code> / <code>Highrise</code> compatible, validation native et chemin rapide mesuré pour l'analyse, la sérialisation et le travail asynchrone de longue durée.
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" />
  <img alt="Async-first" src="https://img.shields.io/badge/Async-first-0A7EA4" />
  <img alt="Oracle parity" src="https://img.shields.io/badge/Strict%20parity-100%25-2E7D32" />
  <img alt="275/275" src="https://img.shields.io/badge/Hot--path%20suite-275%2F275-0A7EA4" />
  <img alt="Custom License" src="https://img.shields.io/badge/License-Custom-red" />
  <img alt="Unofficial Highrise" src="https://img.shields.io/badge/Highrise-Unofficial-orange" />
</p>

<p align="center">
  <code>highrise-bot-python</code> · import <code>highrise_fast</code> · uniquement sur GitHub, pas sur PyPI
</p>

Ce projet est non officiel et n'est ni affilié, ni approuvé, ni pris en charge par Highrise ou Pocket Worlds.

---

## Aperçu

Enregistré sur **Python 3.11.9 / Windows 10**, en utilisant le SDK officiel Highrise comme oracle d'acceptation/refus.

| Preuve | Résultat |
| --- | ---: |
| Suite du chemin chaud | **275 / 275** validées, 0 erreur |
| Parité stricte avec l'oracle (250 000 charges utiles adversariales) | **100 % de correspondance, dans les deux sens** |
| Parité stricte avec l'oracle (80 395 cas uniques générés) | **80 395 / 80 395** |
| Sérialisation vs. officielle | **16,00× CPU · 15,24× temps réel** |
| Désérialisation vs. officielle | **4,00× CPU · 4,16× temps réel** |
| Analyse tolérante soutenue, 10 s | **2 080 153 ops · 208 015 ops/s · 0 erreur** |
| P99 du parsing de chat | **4,40 µs** |
| Sérialisation de chat (`orjson`) | **0,409 µs / op** |
| Fuites de requêtes annulées | **0** |
| Croissance d'objets sur 50 000 analyses | **+0** |

Ce sont des microbenchmarks locaux du chemin chaud du SDK. Ils ne représentent pas le débit réseau complet de Highrise.

---

## Table des matières

- [Pourquoi ce SDK](#pourquoi-ce-sdk)
- [Vue d'ensemble](#vue-densemble)
- [Installation](#installation)
- [Démarrage rapide](#demarrage-rapide)
- [Lancement sous Windows](#lancement-sous-windows)
- [API du bot](#api-du-bot)
- [Validation](#validation)
- [Déboguer des charges utiles invalides](#debuguer-des-charges-utiles-invalides)
- [Performance](#performance)
- [Compatibilité](#compatibilite)
- [Architecture](#architecture)
- [Environnement](#environnement)
- [Migration](#migration)
- [Compromis](#compromis)
- [Sécurité](#securite)
- [Licence](#licence)
- [Crédits](#credits)

---

## Pourquoi ce SDK

Le package officiel [`highrise-bot-sdk`](https://pypi.org/project/highrise-bot-sdk/) (`25.1.0`) est l'implémentation de référence. Il est construit autour de `aiohttp`, `cattrs`, `quattro` et `pendulum`.

`highrise_fast` conserve le même modèle mental pour les bots :

- gestionnaires `BaseBot`
- méthodes `Highrise`
- mêmes noms `_type` sur le réseau
- API Web + exécuteur CLI

et remplace le chemin chaud par une construction directe des modèles, un codec `orjson` optionnel, un validateur natif et un nettoyage explicite du registre des requêtes.

Le SDK officiel reste l'**oracle**. Le mode strict est évalué par rapport à lui. La compatibilité est mesurée, pas supposée.

Sources officielles :

- https://github.com/pocketzworld/python-bot-sdk
- https://pypi.org/project/highrise-bot-sdk/
- https://create.highrise.game/

---

## Vue d'ensemble

| | Officiel `25.1.0` | `highrise_fast` |
| --- | :---: | :---: |
| `BaseBot` / `Highrise` / API Web / CLI | Oui | Oui |
| Gestionnaires d'événements | 12 + cycle de vie | Identique, plus `on_invalid_packet` |
| Méthodes publiques `Highrise` | 34 | Identique, plus `fail_pending` / `mark_state_synced` |
| Types de requêtes sortantes | 33 | 33 |
| Événements entrants en salle | 11 | 11 |
| Tuples `GetRoomUsersResponse` | Échec connu de `cattrs` en benchmark | Analysés |
| Validation stricte native | — | Oui |
| Bornes sémantiques | — | Oui |
| Erreurs codées par raison | — | Oui |
| Chemin rapide `orjson` | — | Oui, avec fallback JSON stdlib |
| Nettoyage des requêtes lors d'annulation | — | `finally` + `fail_pending` |
| Mode fire-and-forget | — | `HR_FAST_FIRE_AND_FORGET` |
| Télémétrie | — | `stats()` / `invalid_packet_stats()` |
| Boucle de réception par défaut | Analyse puis dispatch | **Validation stricte, puis dispatch** |

---

## Installation

Windows 10 / 11 avec Python **3.11+**. Distribué uniquement via GitHub.

```bat
python -m pip install "git+https://github.com/Tenslaster/highrise-bot-python.git"
```

Depuis un clone local :

```bat
python -m pip install .
```

Runtime :

| Dépendance | Rôle |
| --- | --- |
| `aiohttp` | Requis pour le client WebSocket + API Web |
| `orjson` | Recommandé pour le chemin JSON rapide ; le JSON stdlib est utilisé s'il est absent |
| `quattro` | Optionnel ; utilise `asyncio.TaskGroup` en fallback |

```bat
python -c "import highrise_fast; print(highrise_fast.__version__)"
python -m highrise_fast --help
```

---

## Démarrage rapide

```python
from highrise_fast import BaseBot, Position

class MyBot(BaseBot):
    async def on_chat(self, user, message):
        if message.lower() == "!ping":
            await self.highrise.chat("pong!")

    async def on_whisper(self, user, message):
        await self.highrise.send_whisper(user.id, f"got it, {user.username}")

    async def on_user_join(self, user, position: Position):
        await self.highrise.chat(f"Bienvenue, {user.username}!")
```

```bat
python -m highrise_fast my_bot:MyBot YOUR_ROOM_ID YOUR_API_TOKEN
```

Pour un usage quotidien, lancez avec un fichier `.bat` à la place : voir [Lancement sous Windows](#lancement-sous-windows).

Programmatique :

```python
import asyncio
from highrise_fast import bot_runner

asyncio.run(bot_runner("my_bot:MyBot", "ROOM_ID", "API_TOKEN"))
```

Les messages privés sont un gestionnaire distinct (`on_whisper`), comme dans le SDK officiel. `on_chat` ne couvre que le chat global de la salle.

---

## Lancement sous Windows

Tout ce qui suit est compatible avec un double-clic. Aucune connaissance du terminal n'est nécessaire.

### 1. Configuration (une fois)

Créez `Setup-Venv.bat` dans votre dossier de bot puis exécutez-le :

```bat
@echo off
cd /d "%~dp0"
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install "git+https://github.com/Tenslaster/highrise-bot-python.git"
echo.
echo Setup complete. Now create bot.env.bat and run Start-Bot.bat
pause
```

### 2. Identifiants

Créez `bot.env.bat` à côté. **Ne le committez jamais.**

```bat
@echo off
set "ROOM_ID=put_your_room_id_here"
set "API_TOKEN=put_your_bot_token_here"
```

Ajoutez-le à `.gitignore` :

```text
bot.env.bat
venv/
logs/
```

### 3. Le lanceur

Créez `Start-Bot.bat` :

```bat
@echo off
cd /d "%~dp0"
color 04
title My Highrise Bot

set "VENV=%~dp0venv\Scripts"
if not exist "%VENV%\python.exe" (
  echo Missing venv - run Setup-Venv.bat first.
  pause
  exit /b 1
)

if not exist "%~dp0bot.env.bat" (
  echo Missing bot.env.bat - create it with ROOM_ID and API_TOKEN.
  pause
  exit /b 1
)
call "%~dp0bot.env.bat"

call "%VENV%\activate.bat"
"%VENV%\python.exe" -c "import platform; print('Bot Python', platform.python_version())"

:loop
echo Starting the bot...
"%VENV%\python.exe" -m highrise_fast my_bot:MyBot %ROOM_ID% %API_TOKEN%
echo Bot crashed or disconnected.
echo Restarting in 10 seconds... (close this window to stop)
timeout /t 10 /nobreak >nul
goto loop
```

Double-cliquez sur `Start-Bot.bat` et le bot est en ligne.

| Partie | Ce qu'elle fait |
| --- | --- |
| `my_bot:MyBot` | `nom_fichier:NomClasse`. `my_bot.py` contenant `class MyBot(BaseBot)` |
| `%ROOM_ID%` / `%API_TOKEN%` | Chargés depuis `bot.env.bat`, donc les secrets restent hors du lanceur |
| `:loop` / `goto loop` | Redémarre le bot 10 secondes après tout crash ou déconnexion |
| `color 04` | Texte rouge, utile pour distinguer les fenêtres de bots |

Pour arrêter le bot, fermez la fenêtre ou appuyez sur `Ctrl+C`.

### Extras optionnels

Définissez les options du SDK avant la ligne de lancement (voir [Environnement](#environnement)) :

```bat
set "HIGHRISE_FAST_VALIDATION=strict"
set "HR_READ_TIMEOUT=90"
```

Démarrez le bot sous Windows : appuyez sur `Win+R`, tapez `shell:startup`, puis déposez un raccourci vers `Start-Bot.bat` dans ce dossier.

Créez un fichier de log en remplaçant la ligne de lancement par :

```bat
if not exist logs mkdir logs
"%VENV%\python.exe" -m highrise_fast my_bot:MyBot %ROOM_ID% %API_TOKEN% >> logs\bot.log 2>&1
```

Supprimez `logs\bot.log` de temps en temps pour éviter qu'il ne grossisse indéfiniment.

---

## API du bot

### Gestionnaires `BaseBot`

Les signatures correspondent au SDK officiel `highrise-bot-sdk 25.1.0`.

| Gestionnaire | Arguments |
| --- | --- |
| `before_start` | `tg` |
| `on_start` | `session_metadata` |
| `on_chat` | `user, message` |
| `on_whisper` | `user, message` |
| `on_emote` | `user, emote_id, receiver` |
| `on_reaction` | `user, reaction, receiver` |
| `on_user_join` | `user, position` |
| `on_user_leave` | `user` |
| `on_tip` | `sender, receiver, tip` |
| `on_channel` | `sender_id, message, tags` |
| `on_user_move` | `user, destination` |
| `on_voice_change` | `users, seconds_left` |
| `on_message` | `user_id, conversation_id, is_new_conversation` |
| `on_moderate` | `moderator_id, target_user_id, moderation_type, duration` |
| `on_invalid_packet` | `exc, raw` — supplémentaire ; appelé lorsqu'un paquet échoue la validation |

Les paquets entrants sont **validés strictement par défaut** avant d'atteindre un gestionnaire. Remplacez `validation_mode="lenient"` sur `BaseBot`, passez `--validation lenient`, ou définissez `HIGHRISE_FAST_VALIDATION=[...]`.

```python
class MyBot(BaseBot):
    def __init__(self):
        super().__init__(
            validation_mode="strict",   # ou "lenient"
            on_invalid="drop",          # ou "raise" / "log-only"
            invalid_warn_cooldown=60.0,
        )

    def on_invalid_packet(self, exc, raw):
        # optionnel ; le comportement par défaut est déjà journalisé + compté
        return None
```

### Méthodes `Highrise`

Toutes les méthodes officielles sont implémentées :

`chat` · `send_whisper` · `send_emote` · `react` · `set_indicator` · `send_channel` · `walk_to` · `teleport` · `get_room_users` · `get_wallet` · `get_backpack` · `change_backpack` · `[...]`

Ajouts :

| Méthode | But |
| --- | --- |
| `fail_pending(message)` | Échoue toutes les RPC en attente lorsque la socket meurt |
| `mark_state_synced()` | Efface `state_dirty` après resynchronisation de l'état de la salle |

`send_channel` accepte aussi `only_to`, qui existe sur le modèle officiel `ChannelRequest` mais n'est pas exposé sur l'helper officiel `Highrise.send_channel`.

```python
await self.highrise.send_channel("ping", tags={"bots"}, only_to={other_bot_id})
```

### API Web

Même points d'entrée publics que l'official : utilisateurs, salles, posts, objets, grabs.

```python
from highrise_fast import WebAPI

api = WebAPI()  # optional base_url=...
room = await api.get_room("ROOM_ID")
print(room)
```

L'API Web Highrise est non authentifiée dans les deux SDK. Les tokens de bot servent à l'API WebSocket bot, pas à ce client.

### CLI

```bat
python -m highrise_fast my_bot:MyBot ROOM_ID API_TOKEN
python -m highrise_fast my_bot:MyBot ROOM_ID API_TOKEN --validation strict --on-invalid drop
python -m highrise_fast my_bot:MyBot ROOM_ID API_TOKEN --extra_bot other:Bot OTHER_ROOM OTHER_TOKEN
```

---

## Validation

```python
from highrise_fast import parse_server_message

event = parse_server_message(data)                              # lenient
event = parse_server_message(data, strict=True)                 # accept/reject officiel
event = parse_server_message(data, strict=True, strict_semantic=True)
```

| Mode | Comportement |
| --- | --- |
| **Lenient** | Construction rapide. Les clés supplémentaires, types inhabituels et charges utiles partielles sont tolérées quand possible. |
| **Strict** | Rejette ce que le SDK officiel rejette. C'est le contrat aligné sur l'oracle. |
| **Strict + semantic** | Strict, plus bornes du projet (coordonnées, longueurs, montants de portefeuille, valeurs enum). |

Codes de raison :

```text
[STRIPPED 75 bytes]
```

La boucle de réception par défaut est strict. `parse_server_message()` reste par défaut en mode lenient pour que les outils ponctuels restent rapides.

---

## Déboguer des charges utiles invalides

`parse_server_message(..., strict=True)` lève `HighriseFastValidationError`.

| Accès | Signification |
| --- | --- |
| `e.errors` | `list[ValidationErrorDetail]` |
| `e.payload` | Dict / JSON rejeté |
| `e.short()` | Ligne de log en une ligne |
| `e.verbose()` | Message + charge utile brute |
| `e.to_dict()` | Enregistrement sérialisable en JSON |

Chaque détail : `.path` · `.message` · `.expected` · `.got` · `.value` · `.reason_code`

```python
from highrise_fast import HighriseFastValidationError, parse_server_message

payload = {
    "_type": "ChatEvent",
    "user": {"id": "u1", "username": "alice"},
    "whisper": False,
}

try:
    parse_server_message(payload, strict=True)
except HighriseFastValidationError as e:
    print(e.short())
    # $.message: missing required string [MISSING_FIELD]
```

```python
payload = {
    "_type": "UserMovedEvent",
    "user": {"id": "u1", "username": "alice"},
    "position": {"x": "12.5", "y": 0.0, "z": 0.0},
}

try:
    parse_server_message(payload, strict=True)
except HighriseFastValidationError as e:
    d = e.errors[0]
    print(d.path, d.expected, d.got, d.reason_code)
    # $.position.x float str WRONG_TYPE
```

```python
import logging
from highrise_fast import HighriseFastValidationError, parse_server_message

log = logging.getLogger("bot.validation")

def parse_payload(data):
    try:
        return parse_server_message(data, strict=True)
    except HighriseFastValidationError as e:
        log.warning("Invalid payload: %s", e.short(), extra={"validation": e.to_dict()})
        return None
```

---

## Performance

Tous les chiffres ci-dessous proviennent des exécutions enregistrées (2026-09-20, Python 3.11.9, Windows 10). Les relances varient selon le CPU, l'horloge et le bruit du processus.

### 1. Suite du chemin chaud

**275 / 275 OK**, 0 erreur, 261 cas chronométrés.

| Catégorie | Cas | Ops/s moy | µs moyen |
| --- | ---: | ---: | ---: |
| Analyse du cœur de la boucle d'événements | 93 | 319 631 | 4,099 |
| Surcharge de validation | 114 | 456 697 | 3,581 |
| Mémoire / GC | 2 chronométrés | 268 364 | 3,926 |
| Pics de logique de jeu | 6 | 5 871 | 356,252 |
| Malicieux / adversariaux | 23 | 307 879 | 4,831 |
| Asyncio | 9 | 16 487 | 335,927 |
| Sortante | 10 | 1 159 355 | 3,092 |
| Comparaison backend JSON | 4 | 636 393 | 2,177 |

#### Analyse entrante (tolérante)

| Charge utile | ops/s | µs/op |
| --- | ---: | ---: |
| `ChatEvent` | 348 614 | 2,869 |
| `EmoteEvent` | 326 861 | 3,059 |
| `UserLeftEvent` | 391 466 | 2,555 |
| `ChannelEvent` | 457 949 | 2,184 |
| `MessageEvent` | 485 484 | 2,060 |
| `UserJoinedEvent` | 220 527 | 4,535 |
| `TipReactionEvent` | 195 603 | 5,112 |
| `GetRoomUsersResponse` | 122 565 | 8,159 |
| `ChatEvent` strict | 174 052 | 5,745 |

#### Sortantes + backends JSON (chat)

| Backend | ops/s | µs/op |
| --- | ---: | ---: |
| dumps `highrise_fast` | 1 800 828 | 0,555 |
| dumps `orjson` | 2 444 988 | 0,409 |
| dumps `ujson` | 904 855 | 1,105 |
| dumps stdlib `json` | 200 578 | 4,986 |
| loads `highrise_fast` | 892 578 | 1,120 |
| loads `orjson` | 806 940 | 1,239 |
| loads `ujson` | 636 699 | 1,571 |
| loads stdlib `json` | 209 356 | 4,777 |

Sur cette machine, le chemin de chargement du SDK a surpassé le JSON stdlib d'environ **4,3×** et était légèrement devant le `orjson` nu car la mesure inclut le modèle typé, pas seulement bytes → dict.

#### Latence et mémoire

| Vérification | Résultat |
| --- | --- |
| Chat parse p99 | 4,400 µs |
| Premier appel à froid | 9,100 µs |
| Pic `tracemalloc` parse chat | 0,855 KB |
| Blocs alloués / appel | 0,003 |
| Pic sur scène de danse (40 évènements) | 163 µs |
| Pic raid (50 jointures/sorties) | 184 µs |
| Pic de pourboires (100) | 499 µs |
| Inventaire 500 objets | 1 068 µs |

### 2. Mothership / Leviathan

250 000 charges utiles adversariales uniques, 2 workers.

| Phase | Résultat |
| --- | --- |
| 1 Génération du nuage | 250 000 charges utiles en 313,35 s |
| 2 Creuset oracle | SDK officiel accept **39 513** · strict personnalisé **39 513** · lenient personnalisé **250 000** |
| Parité stricte | **100 % de correspondance, dans les deux sens** |
| 3 Vitesse sur le réseau | Sérialisation **16,00×** CPU / **15,24×** temps réel · désérialisation **4,00×** / **4,16×** |
| 4 Concurrence | 200 requêtes annulées → registre des requêtes en attente **propre** |
| 5 Mémoire | 1 GC sur 5k analyses (faible pression) · pic **88,3 KB** · aucune refcycle |
| 6 Robustesse adversariale | Regex, surrogate UTF-8, NaN, entier énorme, imbrication profonde → **5 / 5** |

Le fait que le mode lenient accepte 250 000 / 250 000 est attendu : le mode lenient est le chemin de résilience. Le strict est le chemin oracle.

### 3. Validation de type à échelle maximale

80 395 cas uniques (exhaustif + pairwise + triplewise + fuzz + adversarial + boundary). Le SDK officiel a classé 10 724 cas/s ; le strict personnalisé 21 071 cas/s.

| | Officiel | Strict personnalisé | Lenient personnalisé |
| --- | ---: | ---: | ---: |
| Accepte | 29 318 | 29 318 | (accepte plus) |
| Rejette | 51 077 | 51 077 | — |
| Correspondance oracle | oracle | **80 395 / 80 395 (100 %)** | 29 318 / 80 395 |
| Qualité du retour | 42,84 / 100 | **100,00 / 100** | — |

Codec + analyse (même exécution) :

| Op | moyenne | p50 | p99 | p99,9 |
| --- | ---: | ---: | ---: | ---: |
| encode | 1,06 µs | 1,10 µs | 1,20 µs | 3,90 µs |
| decode | 1,95 µs | 2,00 µs | 2,40 µs | 22,30 µs |
| round trip | 2,40 µs | 2,30 µs | 2,80 µs | 33,10 µs |
| parse lenient | 4,24 µs | 4,50 µs | 5,10 µs | 29,50 µs |
| parse strict | 7,44 µs | 7,70 µs | 9,50 µs | 34,80 µs |

Analyse soutenue sur 10 s en mode lenient :

```text
2 080 153 ops en 10,00 s
208 015 ops/s
0 erreur
p50  3,20 µs
p95  4,90 µs
p99  5,40 µs
p99.9  25,20 µs
p99.99 133,50 µs
```

Audit des ressources (même exécution) :

```text
Collections GC pendant 50k analyses : 0
Croissance du nombre d'objets        : +0
tracemalloc peak (20k round-trip)    : 8,3 KB
Fuite de requêtes annulées (200)     : 0
User / Position WeakRef              : collecté
```

### Comment fonctionne l'audit oracle

```text
generate (exhaustif / pairwise / triplewise / fuzz / adversarial / boundary)
        │
        ▼
official SDK  ── accept / reject = ground truth
        │
        ▼
highrise_fast lenient     highrise_fast strict
        │                         │
        └──────── compare ────────┘
```

L'implémentation officielle n'est pas « évaluée ». Elle définit le contrat. Le strict personnalisé doit correspondre dans les deux sens : accepter ce qu'il accepte, rejeter ce qu'il rejette.

---

## Compatibilité

```text
Highrise server
      │
      ▼
  JSON / WebSocket
      │
      ├──────────────► official SDK  (oracle)
      │
      └──────────────► highrise_fast
                         ├─ orjson / stdlib JSON
                         ├─ modèles typés
                         ├─ validation stricte + sémantique
                         └─ diagnostics orientés chemin
```

Suivi par rapport à `25.1.0` officiel :

- noms `_type` de requêtes et formes des champs
- noms `_type` des événements et signatures des gestionnaires
- tuples `GetRoomUsersResponse` `(User, Position | AnchorPosition)`
- points d'entrée de l'API Web et paramètres de requête
- CLI `module:Class ROOM_ID TOKEN` plus `--extra_bot`
- keepalive, abonnements, reconnexion, métadonnées de session du plan de contrôle

Les internals sont intentionnellement différents. N'assumez pas que des types `cattrs` / `attrs`, datetimes `pendulum`, ou des helpers privés officiels existent ici.

Les classes de requête import-compatible (`ChatRequest`, `GetRoomUsersRequest`, …) vivent dans `highrise_fast.models` via `compat_requests.py`. Elles servent au code utilisateur qui construit des requêtes de style officiel.

---

## Architecture

```text
                    ┌─────────────────────┐
                    │     Highrise API    │
                    └──────────┬──────────┘
                               │
                        WebSocket / API Web
             ┌─────────────────┴─────────────────┐
             ▼                                   ▼
      Événements entrants                  Requêtes sortantes
             │                                   │
        JSON decode                           Modèle → réseau
             │                                   │
        ┌─────┴─────┐                       ┌─────┴─────┐
        ▼           ▼                       ▼           ▼
     Lenient     Strict                 stdlib JSON   orjson
        │           │                       │           │
        └─────┬─────┘                       └─────┬─────┘
              ▼                                   ▼
        Modèles typés                     Trame WebSocket
              └─────────────────┬─────────────────┘
                                ▼
                         Logique de bot asynchrone
```

```text
highrise_fast/
├── __init__.py          Highrise, BaseBot, dispatch, codec, CLI
├── __main__.py          python -m highrise_fast
├── models.py            événements, réponses, User / Position / Item / ...
├── models_webapi.py     wrappers de réponse de l'API Web
├── validation.py        validateur strict + sémantique, codes de raison
└── compat_requests.py   shims de *Request de style officiel
```

---

## Environnement

| Variable | Valeur par défaut | But |
| --- | --- | --- |
| `HR_BOTAPI_URL` | `wss://highrise.game/web/botapi` | WebSocket du bot |
| `HR_WEBAPI_URL` | `https://webapi.highrise.game` | API Web |
| `HR_READ_TIMEOUT` | `60` | Temps d'attente de lecture du WebSocket (secondes) |
| `HR_WEBAPI_TIMEOUT` | `30` | Timeout HTTP |
| `HR_FAST_FIRE_AND_FORGET` | `0` | Ignore l'attente des ACK de requête |
| `HR_SDK_NAME` | `highrise-fast` | Nom du user-agent |
| `HR_SDK_USER_AGENT` | `highrise-fast/1.0.0` | User-agent complet |
| `SDK_FAST_REQ_TIMEOUT` / `HR_SDK_REQ_TIMEOUT` | `0` | Timeout par requête (`0` = attendre indéfiniment) |
| `HIGHRISE_FAST_VALIDATION` | `strict` | Mode de boucle de réception : `strict` \| `lenient` |
| `HIGHRISE_FAST_ON_INVALID` | `drop` | `drop` \| `raise` \| `log-only` |
| `HIGHRISE_FAST_INVALID_WARN_COOLDOWN` | `60` | Secondes entre deux avertissements pour paquets invalides identiques |

Dans un lanceur `.bat` :

```bat
set "HR_READ_TIMEOUT=90"
set "HIGHRISE_FAST_VALIDATION=strict"
python -m highrise_fast my_bot:MyBot ROOM_ID TOKEN
```

---

## Migration

```python
# officiel
from highrise import BaseBot

# ce SDK
from highrise_fast import BaseBot
```

Les noms des gestionnaires et des méthodes `self.highrise.*` sont les mêmes. Remplacez simplement l'import, exécutez votre bot dans une salle de test, puis passez en production.

Ce qui n'est pas identique :

| Sujet | Remarque |
| --- | --- |
| Package | `highrise` → `highrise_fast` |
| Modèles | dataclasses / slots, pas `attrs` |
| `on_chat` | `(user, message)` — les whispers vont vers `on_whisper` |
| `react` / `on_reaction` | `str` au runtime ; mêmes valeurs autorisées que `Reaction` officiel |
| Constructeur API Web | `WebAPI()` ou `WebAPI(base_url=...)` — pas de `token=` |
| Boucle de réception par défaut | validation stricte ; l'officiel n'a pas de garde équivalente |
| Dépendances | pas de `cattrs` / `pendulum` / `click` sur le chemin principal |

Validez un bot en direct avant de basculer une flotte. Le contrat réseau est testée ; votre logique de bot ne l'est pas.

Disposition suggérée :

```text
my_highrise_bot/
├── my_bot.py
├── Setup-Venv.bat
├── Start-Bot.bat
├── bot.env.bat      # jamais committer
└── venv/
```

Gardez les tokens hors de git. Vous n'avez pas besoin d'empaqueter `highrise_fast/` dans chaque bot si vous installez le package.

---

## Compromis

1. **Non officiel.** Aucun support de Pocket Worlds.
2. **Python 3.11+.** L'officiel déclare encore 3.10.
3. **L'import peut être plus lourd** lorsque `orjson` charge son extension native. Ce coût est unique par processus, pas par message.
4. **Le mode strict coûte du CPU.** Sur la version v3 enregistrée, l'analyse tolérante moyenne était de 4,24 µs et le strict de 7,44 µs. C'est le prix des vérifications oracle.
5. **Lenient n'est pas l'oracle.** Lenient acceptera des charges utiles que l'officiel rejette. Utilisez strict quand vous vous souciez du contrat officiel.
6. **La compatibilité est testée, pas supposée.** Des noms de fonctions identiques ne sont pas une preuve. La preuve est la suite oracle.

---

## Sécurité

Ne mettez pas les tokens de l'API Highrise dans ce README, dans le dépôt, les logs, les captures d'écran ou les traces d'exception.

Gardez le token dans `bot.env.bat` (voir [Lancement sous Windows](#lancement-sous-windows)) et ajoutez ce fichier à `.gitignore`. Si un token fuit, faites-le tourner dans le Creator Portal.

Le parseur est une frontière de processus, pas un substitut à la sécurité côté serveur. La suite adversariale couvre les types inattendus, champs manquants, chaînes surdimensionnées, entiers gigantesques, imbrications profondes, Unicode étrange, etc.

Voir [`SECURITY.md`](SECURITY.md).

---

## Licence

Licence personnalisée — pas MIT, Apache, BSD, ni GPL.

Lisez [`LICENSE.md`](LICENSE.md) avant toute redistribution, fork ou intégration dans un autre produit.

---

## Crédits

- Highrise Creator docs : https://create.highrise.game/
- SDK Python officiel (Pocket Worlds) : https://github.com/pocketzworld/python-bot-sdk
- `orjson` : https://github.com/ijl/orjson

Implémentation indépendante autour de l'API publique des bots et du comportement observé du SDK officiel.

---

## Dépôt

- Ce projet : https://github.com/Tenslaster/highrise-bot-python
- SDK officiel : https://github.com/pocketzworld/python-bot-sdk

<p align="center">
  <strong>Chemin chaud mesuré. Mode strict aligné sur l'oracle. Conçu pour les bots qui restent en ligne.</strong>
</p>
