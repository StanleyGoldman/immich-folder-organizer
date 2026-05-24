FROM node:20

ARG TZ
ENV TZ="$TZ"

# Install basic development tools and Python 3
RUN apt-get update && apt-get install -y --no-install-recommends \
  less \
  git \
  ripgrep \
  procps \
  sudo \
  fzf \
  zsh \
  man-db \
  zip \
  unzip \
  gnupg2 \
  gh \
  jq \
  nano \
  vim \
  curl \
  make \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  locales \
  && echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
  && locale-gen \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Grant passwordless sudo to the default user
RUN echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
  && chmod 0440 /etc/sudoers.d/$USERNAME

# Persist bash history on a named volume.
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R $USERNAME /commandhistory

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

# Create workspace and Claude config directories.
# The host repo is bind-mounted at /workspace/immich-folder-organizer by compose;
# /home/node/.claude is backed by a named volume so it survives rebuilds.
RUN mkdir -p /workspace/immich-folder-organizer /home/node/.claude && \
  chown -R node:node /workspace /home/node/.claude

WORKDIR /workspace/immich-folder-organizer

ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  wget "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  sudo dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

USER node

ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

RUN npm install -g pyright

ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano

# Powerline10k zsh setup with history persistence + fzf
ARG ZSH_IN_DOCKER_VERSION=1.2.0
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
  -p git \
  -p fzf \
  -a "source /usr/share/doc/fzf/examples/key-bindings.zsh" \
  -a "source /usr/share/doc/fzf/examples/completion.zsh" \
  -a "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  -x

# Add ~/.local/bin to PATH for user-installed binaries (e.g. Claude)
RUN echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/node/.bashrc \
  && echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/node/.zshrc

# Install uv for fast Python env / package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Pre-create the venv so the VS Code Python extension finds it on first open
RUN uv venv /workspace/immich-folder-organizer/.venv
