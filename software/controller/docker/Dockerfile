# using base-image containing python3.9, setting shell to use bash by default, switching to /root folder
FROM python:3.12 as build_image
SHELL ["/bin/bash", "-c"]
WORKDIR /root

# install jq and moreutils (-> sponge)
RUN apt update
RUN apt install -y jq moreutils

# install poetry and set up a venv
RUN python3.12 -m pip install --upgrade pip
RUN python3.12 -m pip install poetry
RUN python3.12 -m venv --copies .venv
RUN source .venv/bin/activate

COPY poetry.lock .
COPY pyproject.toml .
COPY README.md .

# install dependencies through poetry
RUN poetry config installer.max-workers 1
RUN poetry install --no-root

COPY config ./config
COPY config/config.template.json ./config/config.json

RUN echo 'ACROPOLIS_HARDWARE_LOCKFILE_PATH="/root/acropolis_hardware.lock"' > ./config/.env

FROM python:3.12-slim

WORKDIR /root
COPY --from=build_image /root/.venv /root/.venv

# copy source directories
COPY src ./src
COPY --from=build_image /root/config ./config

ENTRYPOINT ["/root/.venv/bin/python3", "/root/src/main.py"]