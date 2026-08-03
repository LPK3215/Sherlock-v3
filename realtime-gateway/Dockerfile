FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy the gateway code. Agent logic remains in the separate Yuxi services.
COPY . .

WORKDIR /runtime

EXPOSE 7860

CMD ["uv", "run", "--project", "/app", "--no-sync", "python", "-u", "/app/bot.py", "--host", "0.0.0.0", "--transport", "webrtc"]
