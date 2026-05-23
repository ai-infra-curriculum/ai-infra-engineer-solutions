# Exercise 02: Docker Walkthrough — Reference Materials

Reference for [learning exercise-02-docker.md](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-101-foundations/exercises/exercise-02-docker.md).

Reference end-state files for the Flask-in-Docker walkthrough.

## Files

```
exercise-02-docker/
├── README.md
├── app.py                   # simple Flask service
├── requirements.txt
├── Dockerfile               # multi-stage, non-root, healthcheck
├── .dockerignore
└── docker-compose.yml       # optional: add a Postgres for local testing
```

## Build + run

```bash
docker build -t hello-flask:0.1 .
docker run -d --rm --name hello -p 8000:8000 hello-flask:0.1
curl http://localhost:8000/health
docker stop hello
```
