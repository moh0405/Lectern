# API image: FastAPI + the RAG engine. The web app is deployed separately.
#   docker build -t ai-study-mentor .
#   docker run -p 8000:8000 --env-file .env ai-study-mentor
# Build without the embedding model (keyword search only, ~1 GB smaller):
#   docker build --build-arg EMBEDDINGS=0 -t ai-study-mentor:lite .

FROM python:3.12-slim AS build
ARG EMBEDDINGS=1
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY backend ./backend
# CPU-only torch: the default wheel pulls ~2 GB of CUDA libraries that a CPU container never uses.
RUN if [ "$EMBEDDINGS" = "1" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install ".[api,sources,math,export,anki,aws,embeddings]"; \
    else \
      pip install ".[api,sources,math,export,anki,aws]"; \
    fi
# Bake the model into the image so the first request does not download it.
ENV HF_HOME=/opt/hf
RUN if [ "$EMBEDDINGS" = "1" ]; then \
      python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')"; \
    else mkdir -p /opt/hf; fi

FROM python:3.12-slim
ENV PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/hf HF_HUB_OFFLINE=1 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UPLOAD_DIR=/data/uploaded_files STORE_DIR=/data/vector_store \
    ANALYTICS_DB=/data/analytics.db STUDY_DB=/data/study.db \
    PORT=8000
COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/hf /opt/hf
# AWS Lambda Web Adapter: lets Lambda talk to this ordinary web server (streaming included).
# Outside Lambda the file is just ignored.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
WORKDIR /app
COPY --chown=app backend ./backend
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import os,urllib.request as u; u.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
CMD ["sh", "-c", "exec uvicorn backend.api:app --host 0.0.0.0 --port ${PORT}"]
