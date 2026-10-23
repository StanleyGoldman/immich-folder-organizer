# Single entry point for checks, used locally and by every CI step
# (.woodpecker/ci.yml), so a green `make ci` predicts a green pipeline.
# See docs/ci.md.

SHELL := bash
.SHELLFLAGS := -o pipefail -c

# Branch that coverage-diff and coverage-base compare against; CI passes
# BASE=origin/<target branch>
BASE ?= origin/main
# Tag suffix for the image check; CI passes TAG=<pipeline number>
TAG ?= local
# Worktree for the merge-base run; must be outside the checkout
BASE_DIR ?= /tmp/immich-folder-organizer-base

.PHONY: ci lint format types test image coverage-diff coverage-base fix

# Run a check, keeping its output in reports/<name>.log and its exit code in
# reports/<name>.status for scripts/ci/pr_report.py, then exit with that code
define check
	@mkdir -p reports
	@$(2) 2>&1 | tee reports/$(1).log; status=$$?; echo $$status > reports/$(1).status; exit $$status
endef

# Every check runs and reports, even after one fails
ci:
	@$(MAKE) -k lint format types test

lint:
	$(call check,lint,uv run ruff check)

format:
	$(call check,format,uv run ruff format --check)

types:
	$(call check,types,uv run mypy)

test:
	$(call check,test,uv run pytest --cov --cov-report=xml:reports/coverage.xml --junitxml=reports/junit.xml)

# Build the production image, record its size in reports/image.size, then
# remove it. Not part of `ci`: needs Docker, and CI runs it as its own step.
image:
	$(call check,image,docker build -t immich-folder-organizer:ci-$(TAG) .)
	@docker image inspect -f '{{.Size}}' immich-folder-organizer:ci-$(TAG) > reports/image.size
	@docker rmi immich-folder-organizer:ci-$(TAG) > /dev/null

# Coverage of the lines changed since $(BASE); reported, never fails the build
coverage-diff:
	-uv run diff-cover reports/coverage.xml --compare-branch=$(BASE) --format json:reports/diff-cover.json

# Test count and total coverage at the merge-base, for the deltas in the PR
# report. Writes reports/base/{coverage,junit}.xml; leaves them absent when the
# base predates uv or its run fails. Never fails the build.
coverage-base:
	-@rm -rf reports/base; mkdir -p reports/base; \
	mb=$$(git merge-base HEAD $(BASE)) || exit 0; \
	git cat-file -e $$mb:uv.lock 2>/dev/null || { echo "coverage-base: $$mb predates uv; skipping"; exit 0; }; \
	git worktree remove --force $(BASE_DIR) 2>/dev/null; rm -rf $(BASE_DIR); \
	git worktree add --detach $(BASE_DIR) $$mb && \
	(cd $(BASE_DIR) && uv run pytest -q --cov --cov-report=xml:$(CURDIR)/reports/base/coverage.xml --junitxml=$(CURDIR)/reports/base/junit.xml) \
	|| rm -f reports/base/*.xml; \
	git worktree remove --force $(BASE_DIR)

# Auto-fix lint findings and formatting (local only)
fix:
	uv run ruff check --fix
	uv run ruff format
