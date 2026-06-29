module github.com/agent-tutor/mcp-gateway

go 1.24.0

require (
	github.com/agent-tutor/agent-tutor-go v0.0.0-00010101000000-000000000000
	github.com/go-chi/chi/v5 v5.2.1
	github.com/google/uuid v1.6.0
	github.com/mark3labs/mcp-go v0.8.3
)

replace github.com/agent-tutor/agent-tutor-go => ../agent-tutor-go

require (
	github.com/xeipuuv/gojsonpointer v0.0.0-20180127040702-4e3ac2762d5f // indirect
	github.com/xeipuuv/gojsonreference v0.0.0-20180127040603-bd5ef7bd5415 // indirect
	github.com/xeipuuv/gojsonschema v1.2.0 // indirect
)

