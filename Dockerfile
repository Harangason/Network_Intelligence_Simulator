FROM node:22-bookworm-slim AS node-runtime

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=development
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=15050
ENV FRONTEND_PORT=13500
ENV SIMULATOR_BACKEND_API_URL=http://127.0.0.1:15050/api

WORKDIR /app

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/backend/requirements.txt

COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN cd /app/frontend && node /usr/local/lib/node_modules/npm/bin/npm-cli.js ci

COPY . /app

EXPOSE 13500 15050

CMD ["python", "generate_realistic_communication_tool.py"]
