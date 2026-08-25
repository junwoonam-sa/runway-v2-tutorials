# 웹 서버, MCP 서버, 정적 UI가 **한 이미지**에 들어갑니다.
#
# 나눌 이유가 없습니다 — MCP 서버는 웹 서버의 자식 프로세스로 돌고, 프런트엔드에는
# 빌드 단계가 없습니다. 배포되는 것은 Deployment 하나, Service 하나, HTTPRoute 하나입니다.
#
# 빌드:
#   docker build -t gitea.<도메인>/<프로젝트조직>/llm-tutorial:0.1.0 app/
#
# 태그를 재사용하지 마세요. kubelet은 이미 받아 둔 이미지를 다시 받지 않으므로
# (imagePullPolicy: IfNotPresent), 같은 태그로 다시 push하면 노드는 옛 이미지를 계속
# 씁니다. 증상이 "코드를 고쳤는데 반영이 안 된다"로 나타납니다.

FROM python:3.12-slim

# 컨테이너 CPU 리밋과 라이브러리 스레드 풀이 어긋나면 심하게 느려집니다. 계산
# 라이브러리는 스레드 풀을 **호스트의 코어 수**로 잡기 때문에, 1코어짜리 컨테이너가
# 64코어 노드에서 64개 스레드를 띄우고 서로 다투게 됩니다. 값은 차트에서 리밋에 맞춰
# 덮어쓰세요.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 로컬 임베딩까지 쓰려면 아래 두 줄의 주석을 푸세요. torch가 딸려 와 이미지가 1.5 GB
# 넘게 커집니다 — 게이트웨이에 임베딩 모델이 있으면 그대로 두는 편이 낫습니다.
# COPY requirements-local-embeddings.txt ./
# RUN pip install --no-cache-dir -r requirements-local-embeddings.txt

COPY chatbot/ ./chatbot/
COPY mcp_server/ ./mcp_server/
COPY frontend/ ./frontend/

# 루트로 돌지 않습니다. 차트의 podSecurityContext와 같은 UID를 씁니다.
RUN useradd --uid 10001 --create-home appuser
USER 10001

EXPOSE 8000
CMD ["uvicorn", "chatbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
