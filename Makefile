.PHONY: help install index search test typecheck mcp clean

help:
	@echo "KDD Toolkit (TypeScript/Bun)"
	@echo ""
	@echo "  make install     Install dependencies"
	@echo "  make index       Index specs/ into .kdd-index/"
	@echo "  make search q=.. Hybrid search"
	@echo "  make test        Run tests"
	@echo "  make typecheck   Type-check with tsc"
	@echo "  make mcp         Start MCP server"
	@echo "  make clean       Remove node_modules and .kdd-index"

install:
	bun install

index:
	bun run packages/cli/src/cli.ts index specs/

search:
	bun run packages/cli/src/cli.ts search --index-path .kdd-index "$(q)"

test:
	bun test

typecheck:
	bunx tsc --build

mcp:
	bun run packages/mcp/src/mcp.ts

clean:
	rm -rf node_modules .kdd-index
