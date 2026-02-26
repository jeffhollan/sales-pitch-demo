FROM mcr.microsoft.com/devcontainers/python:3.12

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# TODO: this also copies in the .env file for prototype
COPY ./ .

RUN uv pip install --system --no-cache --prerelease=allow -e ".[agent]"

EXPOSE 8088

CMD ["sales-prep-server"]
