FROM python:3.10-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
	POETRY_VERSION=1.7.1

WORKDIR /app


# switch to root for apt commands
USER root
RUN apt update
RUN pip install "poetry==$POETRY_VERSION"

RUN apt update && apt install -y fuse libfuse2
RUN pip install fusepy==2.0.4 mysql-connector-python

# Installiere MySQL-Client
RUN apt update && apt install -y default-mysql-client


# switch back to normal user
#USER 1000


ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8050

