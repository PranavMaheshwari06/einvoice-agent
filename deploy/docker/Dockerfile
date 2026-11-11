FROM python:3.12-slim

# tesseract with German data for extraction/ocr.py; make and git for the dev container.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu make git \
    && rm -rf /var/lib/apt/lists/*

# Same uid as the usual first host user, so files written into the mounted repo stay editable.
RUN useradd --create-home --uid 1000 dev
WORKDIR /workspace

# requirements.lock starts with the PyTorch CPU index; the default wheels bring CUDA.
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY pyproject.toml README.md LICENSE ./
COPY src src
RUN pip install --no-cache-dir --no-deps -e .

ENV HF_HOME=/home/dev/.cache/huggingface
# The mlflow service mounts its volume at /home/dev/mlflow; a volume over a missing path is root-owned.
RUN mkdir -p $HF_HOME /home/dev/mlflow && chown -R dev:dev /home/dev/.cache /home/dev/mlflow
USER dev
