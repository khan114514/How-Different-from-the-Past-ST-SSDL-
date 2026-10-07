FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.0.2 scipy==1.14.1 scikit-learn==1.5.2
RUN groupadd -g 1000 candidate && useradd -u 1000 -g 1000 -m candidate && mkdir -p /workspace/solution /run/forecastcli/queue && chown -R 1000:1000 /workspace /run/forecastcli
COPY cli/*.py /opt/forecastcli/
COPY public_assets/ /workspace/public_assets/
COPY engine/ /opt/forecast-engine/
COPY verifier_assets/ /opt/verifier-assets/
COPY solution/ /workspace/solution/
COPY instruction.md /workspace/instruction.md
COPY task.toml /workspace/task.toml
COPY test.sh /tests/test.sh
RUN chmod 700 /tests && chmod 755 /tests/test.sh
RUN chmod -R a-w /workspace/public_assets /opt/forecast-engine && chmod 700 /opt/verifier-assets && chmod -R go-rwx /opt/verifier-assets && chown root:root /workspace && chmod 555 /workspace && chown -R 1000:1000 /workspace/solution && mkdir -p /logs/agent /logs/artifacts /logs/verifier && chown 1000:1000 /logs/agent /logs/artifacts && chmod 700 /logs/verifier
ENV HOME=/home/candidate PATH=/usr/local/bin:/usr/bin:/bin FORECAST_LANE=gpt PYTHONPATH=/opt/forecastcli OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
USER root
WORKDIR /workspace/solution
ENTRYPOINT ["python","-I","/opt/forecast-engine/start_task.py"]
CMD ["sleep","infinity"]
