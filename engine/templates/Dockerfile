FROM node:24-bookworm-slim AS ui
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv/app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=ui /build/dist /srv/ui
ENV TWIN_FRONTEND_DIST=/srv/ui PYTHONUNBUFFERED=1
USER 65532:65532
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
