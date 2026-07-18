package command

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/LVTD-LLC/djass/cli/internal/api"
)

const (
	defaultBaseURL      = "https://djass.dev/api/v1"
	maxPayloadBytes     = 1 << 20
	minimumPollInterval = 250 * time.Millisecond
	exitUsage           = 2
	exitConfig          = 3
	exitAPI             = 4
	exitOperation       = 5
)

var Version = "dev"

type stringList []string

func (values *stringList) String() string { return strings.Join(*values, ",") }
func (values *stringList) Set(value string) error {
	*values = append(*values, value)
	return nil
}

type runner struct {
	ctx    context.Context
	client *api.Client
	stdout io.Writer
	stderr io.Writer
}

func Run(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	global := flag.NewFlagSet("djass", flag.ContinueOnError)
	global.SetOutput(io.Discard)
	baseURL := global.String("base-url", envOrDefault("DJASS_BASE_URL", defaultBaseURL), "Djass API base URL")
	apiKey := os.Getenv("DJASS_API_KEY")
	showVersion := global.Bool("version", false, "print the CLI version")
	global.Usage = func() { writeUsage(stderr) }
	if err := global.Parse(args); err != nil {
		return writeError(stderr, exitUsage, err)
	}
	remaining := global.Args()
	if *showVersion {
		fmt.Fprintln(stdout, Version)
		return 0
	}
	if len(remaining) == 0 {
		writeUsage(stderr)
		return exitUsage
	}
	if remaining[0] == "version" {
		fmt.Fprintln(stdout, Version)
		return 0
	}
	if remaining[0] == "help" {
		writeUsage(stdout)
		return 0
	}

	client, err := api.NewClient(*baseURL, apiKey, nil)
	if err != nil {
		return writeError(stderr, exitConfig, err)
	}
	client.SetUserAgent("djass-cli/" + Version)
	r := &runner{ctx: ctx, client: client, stdout: stdout, stderr: stderr}

	switch remaining[0] {
	case "options":
		if len(remaining) != 1 {
			return writeError(stderr, exitUsage, errors.New("usage: djass options"))
		}
		return r.options()
	case "projects":
		if apiKey == "" {
			return writeError(stderr, exitConfig, errors.New("DJASS_API_KEY is required for project commands"))
		}
		return r.projects(remaining[1:])
	case "generate":
		if apiKey == "" {
			return writeError(stderr, exitConfig, errors.New("DJASS_API_KEY is required for generate"))
		}
		return r.generate(remaining[1:])
	default:
		return writeError(stderr, exitUsage, fmt.Errorf("unknown command %q", remaining[0]))
	}
}

func (r *runner) options() int {
	result, err := r.client.Options(r.ctx)
	if err != nil {
		return writeError(r.stderr, exitAPI, err)
	}
	return r.writeJSON(result)
}

func (r *runner) projects(args []string) int {
	if len(args) == 0 {
		return writeError(r.stderr, exitUsage, errors.New("usage: djass projects <create|list|get|status|download>"))
	}
	switch args[0] {
	case "create":
		return r.create(args[1:])
	case "list":
		return r.list(args[1:])
	case "get":
		id, code := parseProjectID(args[1:], "get", r.stderr)
		if code != 0 {
			return code
		}
		project, err := r.client.GetProject(r.ctx, id)
		if err != nil {
			return writeError(r.stderr, exitAPI, err)
		}
		return r.writeJSON(project)
	case "status":
		id, code := parseProjectID(args[1:], "status", r.stderr)
		if code != 0 {
			return code
		}
		status, err := r.client.ProjectStatus(r.ctx, id)
		if err != nil {
			return writeError(r.stderr, exitAPI, err)
		}
		return r.writeJSON(status)
	case "download":
		return r.download(args[1:])
	default:
		return writeError(r.stderr, exitUsage, fmt.Errorf("unknown projects command %q", args[0]))
	}
}

func (r *runner) create(args []string) int {
	payload, code := parseCreatePayload(args, r.stderr)
	if code != 0 {
		return code
	}
	result, err := r.client.CreateProject(r.ctx, payload)
	if err != nil {
		return writeError(r.stderr, exitAPI, err)
	}
	return r.writeJSON(result)
}

func (r *runner) list(args []string) int {
	flags := flag.NewFlagSet("projects list", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	limit := flags.Int("limit", 20, "maximum projects to return (1-100)")
	offset := flags.Int("offset", 0, "number of projects to skip")
	status := flags.String("status", "", "filter by queued, generating, ready, or failed")
	if err := flags.Parse(args); err != nil {
		return writeError(r.stderr, exitUsage, err)
	}
	if flags.NArg() != 0 || *limit < 1 || *limit > 100 || *offset < 0 {
		return writeError(r.stderr, exitUsage, errors.New("usage: djass projects list [--limit 20] [--offset 0] [--status ready]"))
	}
	if *status != "" && *status != "queued" && *status != "generating" && *status != "ready" && *status != "failed" {
		return writeError(r.stderr, exitUsage, fmt.Errorf("invalid status %q", *status))
	}
	result, err := r.client.ListProjects(r.ctx, *limit, *offset, *status)
	if err != nil {
		return writeError(r.stderr, exitAPI, err)
	}
	return r.writeJSON(result)
}

func (r *runner) download(args []string) int {
	if len(args) == 0 || strings.HasPrefix(args[0], "-") {
		return writeError(r.stderr, exitUsage, errors.New("usage: djass projects download <id> [--output project.zip] [--force]"))
	}
	id, code := parseProjectID(args[:1], "download", r.stderr)
	if code != 0 {
		return code
	}
	flags := flag.NewFlagSet("projects download", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	output := flags.String("output", "", "ZIP output path (default: project-<id>.zip)")
	force := flags.Bool("force", false, "overwrite an existing file")
	if err := flags.Parse(args[1:]); err != nil {
		return writeError(r.stderr, exitUsage, err)
	}
	if flags.NArg() != 0 {
		return writeError(r.stderr, exitUsage, errors.New("usage: djass projects download <id> [--output project.zip] [--force]"))
	}
	if *output == "" {
		*output = fmt.Sprintf("project-%d.zip", id)
	}
	file, stagingPath, err := openArtifactOutput(*output, *force)
	if err != nil {
		return writeError(r.stderr, exitOperation, err)
	}
	completed := false
	defer func() {
		if !completed {
			_ = os.Remove(stagingPath)
		}
	}()
	size, err := r.client.DownloadProject(r.ctx, id, file)
	if err != nil {
		file.Close()
		return writeError(r.stderr, exitAPI, err)
	}
	if err := file.Close(); err != nil {
		return writeError(r.stderr, exitOperation, fmt.Errorf("close output file: %w", err))
	}
	if stagingPath != *output {
		if err := os.Rename(stagingPath, *output); err != nil {
			return writeError(r.stderr, exitOperation, fmt.Errorf("replace output file: %w", err))
		}
	}
	completed = true
	absOutput, _ := filepath.Abs(*output)
	return r.writeJSON(map[string]any{"project_id": id, "output": absOutput, "size_bytes": size})
}

func (r *runner) generate(args []string) int {
	flags := flag.NewFlagSet("generate", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	name := flags.String("name", "", "project name")
	slug := flags.String("slug", "", "project slug")
	payloadFile := flags.String("payload", "", "JSON file with the full API create payload")
	output := flags.String("output", "", "empty destination directory (default: project slug)")
	pollInterval := flags.Duration("poll-interval", 2*time.Second, "status polling interval")
	timeout := flags.Duration("timeout", 10*time.Minute, "maximum generation wait")
	var settings stringList
	flags.Var(&settings, "set", "generator option key=value (repeatable)")
	if err := flags.Parse(args); err != nil {
		return writeError(r.stderr, exitUsage, err)
	}
	if flags.NArg() != 0 || *pollInterval < minimumPollInterval || *timeout <= 0 {
		return writeError(r.stderr, exitUsage, errors.New("usage: djass generate --name NAME --slug SLUG [--set key=value] [--output DIR]"))
	}
	payload, err := buildPayload(*payloadFile, *name, *slug, settings)
	if err != nil {
		return writeError(r.stderr, exitUsage, err)
	}
	if *output == "" {
		*output = fmt.Sprint(payload["project_slug"])
	}
	if err := ensureEmptyDestination(*output); err != nil {
		return writeError(r.stderr, exitOperation, err)
	}

	result, err := r.client.CreateProject(r.ctx, payload)
	if err != nil {
		return writeError(r.stderr, exitAPI, err)
	}
	fmt.Fprintf(r.stderr, "Queued project %d; waiting for the generated artifact...\n", result.Project.ID)

	waitContext, cancel := context.WithTimeout(r.ctx, *timeout)
	defer cancel()
	status, err := r.waitForProject(waitContext, result.Project.ID, *pollInterval)
	if err != nil {
		return writeError(r.stderr, exitOperation, err)
	}
	if status.Status == "failed" {
		message := status.ErrorMessage
		if message == "" {
			message = "project generation failed"
		}
		return writeError(r.stderr, exitOperation, errors.New(message))
	}
	archive, err := os.CreateTemp("", "djass-project-*.zip")
	if err != nil {
		return writeError(r.stderr, exitOperation, fmt.Errorf("create temporary artifact: %w", err))
	}
	archivePath := archive.Name()
	defer os.Remove(archivePath)
	size, err := r.client.DownloadProject(r.ctx, result.Project.ID, archive)
	if err != nil {
		archive.Close()
		return writeError(r.stderr, exitAPI, err)
	}
	if err := archive.Close(); err != nil {
		return writeError(r.stderr, exitOperation, fmt.Errorf("close temporary artifact: %w", err))
	}
	if err := extractZIPFileAtomic(archivePath, *output); err != nil {
		return writeError(r.stderr, exitOperation, err)
	}
	absOutput, _ := filepath.Abs(*output)
	return r.writeJSON(map[string]any{
		"project_id": result.Project.ID,
		"status":     status.Status,
		"output":     absOutput,
		"size_bytes": size,
	})
}

func (r *runner) waitForProject(ctx context.Context, id int, interval time.Duration) (api.ProjectStatus, error) {
	for {
		status, err := r.client.ProjectStatus(ctx, id)
		if err != nil {
			return api.ProjectStatus{}, err
		}
		if status.Status == "failed" || (status.Status == "ready" && status.ArtifactReady) {
			return status, nil
		}
		timer := time.NewTimer(interval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return api.ProjectStatus{}, fmt.Errorf("timed out waiting for project %d: %w", id, ctx.Err())
		case <-timer.C:
		}
	}
}

func parseCreatePayload(args []string, stderr io.Writer) (map[string]any, int) {
	flags := flag.NewFlagSet("projects create", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	name := flags.String("name", "", "project name")
	slug := flags.String("slug", "", "project slug")
	payloadFile := flags.String("payload", "", "JSON file with the full API create payload")
	var settings stringList
	flags.Var(&settings, "set", "generator option key=value (repeatable)")
	if err := flags.Parse(args); err != nil {
		return nil, writeError(stderr, exitUsage, err)
	}
	if flags.NArg() != 0 {
		return nil, writeError(stderr, exitUsage, errors.New("usage: djass projects create --name NAME --slug SLUG [--set key=value]"))
	}
	payload, err := buildPayload(*payloadFile, *name, *slug, settings)
	if err != nil {
		return nil, writeError(stderr, exitUsage, err)
	}
	return payload, 0
}

func buildPayload(payloadFile, name, slug string, settings []string) (map[string]any, error) {
	payload := make(map[string]any)
	if payloadFile != "" {
		file, err := os.Open(payloadFile)
		if err != nil {
			return nil, fmt.Errorf("read payload file: %w", err)
		}
		defer file.Close()
		info, err := file.Stat()
		if err != nil {
			return nil, fmt.Errorf("inspect payload file: %w", err)
		}
		if info.Size() > maxPayloadBytes {
			return nil, fmt.Errorf("payload file exceeds the %d MiB safety limit", maxPayloadBytes>>20)
		}
		limited := &io.LimitedReader{R: file, N: maxPayloadBytes + 1}
		decoder := json.NewDecoder(limited)
		if err := decoder.Decode(&payload); err != nil {
			return nil, fmt.Errorf("decode payload file: %w", err)
		}
		var trailing any
		if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
			if err == nil {
				return nil, errors.New("decode payload file: only one JSON object is allowed")
			}
			return nil, fmt.Errorf("decode payload file: %w", err)
		}
	}
	if name != "" {
		payload["project_name"] = name
	}
	if slug != "" {
		payload["project_slug"] = slug
	}
	for _, setting := range settings {
		key, value, ok := strings.Cut(setting, "=")
		if !ok || strings.TrimSpace(key) == "" {
			return nil, fmt.Errorf("invalid --set %q; expected key=value", setting)
		}
		payload[strings.TrimSpace(key)] = value
	}
	if !nonEmptyString(payload["project_name"]) || !nonEmptyString(payload["project_slug"]) {
		return nil, errors.New("project name and slug are required (use --name/--slug or --payload)")
	}
	return payload, nil
}

func nonEmptyString(value any) bool {
	text, ok := value.(string)
	return ok && strings.TrimSpace(text) != ""
}

func parseProjectID(args []string, command string, stderr io.Writer) (int, int) {
	if len(args) != 1 {
		return 0, writeError(stderr, exitUsage, fmt.Errorf("usage: djass projects %s <id>", command))
	}
	id, err := strconv.Atoi(args[0])
	if err != nil || id < 1 {
		return 0, writeError(stderr, exitUsage, errors.New("project id must be a positive integer"))
	}
	return id, 0
}

func openArtifactOutput(path string, force bool) (*os.File, string, error) {
	if force {
		file, err := os.CreateTemp(filepath.Dir(path), ".djass-download-*.tmp")
		if err != nil {
			return nil, "", fmt.Errorf("create temporary output file: %w", err)
		}
		return file, file.Name(), nil
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0o600)
	if err != nil {
		if os.IsExist(err) {
			return nil, "", fmt.Errorf("output file %q already exists; pass --force to overwrite it", path)
		}
		return nil, "", fmt.Errorf("create output file: %w", err)
	}
	return file, path, nil
}

func (r *runner) writeJSON(value any) int {
	var data []byte
	var err error
	if raw, ok := value.(json.RawMessage); ok {
		var pretty bytes.Buffer
		err = json.Indent(&pretty, raw, "", "  ")
		data = pretty.Bytes()
	} else {
		data, err = json.MarshalIndent(value, "", "  ")
	}
	if err != nil {
		return writeError(r.stderr, exitOperation, fmt.Errorf("encode output: %w", err))
	}
	_, err = fmt.Fprintln(r.stdout, string(data))
	if err != nil {
		return writeError(r.stderr, exitOperation, fmt.Errorf("write output: %w", err))
	}
	return 0
}

func writeError(stderr io.Writer, code int, err error) int {
	var apiErr *api.Error
	if errors.As(err, &apiErr) {
		payload := map[string]any{"error": map[string]any{
			"code": apiErr.Code, "category": apiErr.Category, "message": apiErr.Message,
			"retryable": apiErr.Retryable, "details": apiErr.Details,
		}}
		data, _ := json.Marshal(payload)
		fmt.Fprintln(stderr, string(data))
		return exitAPI
	}
	errorCode := "operation_error"
	category := "operation"
	switch code {
	case exitUsage:
		errorCode, category = "usage_error", "usage"
	case exitConfig:
		errorCode, category = "configuration_error", "configuration"
	}
	payload := map[string]any{"error": map[string]any{
		"code": errorCode, "category": category, "message": err.Error(),
		"retryable": false, "details": map[string]any{"exit_code": code},
	}}
	data, _ := json.Marshal(payload)
	fmt.Fprintln(stderr, string(data))
	return code
}

func writeUsage(output io.Writer) {
	fmt.Fprintln(output, `Djass generates production-ready Django SaaS repositories through djass.dev.

Usage:
  djass [--base-url URL] <command>

Commands:
  generate           Create, wait for, download, and safely extract a repository
  options            Print the live generator option catalog
  projects create    Queue a project generation job
  projects list      List projects
  projects get       Get a project
  projects status    Get project generation status
  projects download  Download a generated ZIP
  version            Print the CLI version

Authentication:
  Set DJASS_API_KEY. Use DJASS_BASE_URL only for staging or local development.

Run a subcommand with -h for its flags.`)
}

func envOrDefault(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
